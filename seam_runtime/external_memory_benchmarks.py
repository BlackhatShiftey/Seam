from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "benchmarks" / "registry" / "memory_benchmarks.json"
REPORT_VERSION = "SEAM-EXTERNAL-MEMORY-BENCHMARK-RUN/1"
PLAN_VERSION = "SEAM-EXTERNAL-MEMORY-BENCHMARK-PLAN/1"


@dataclass(frozen=True)
class ExternalBenchmark:
    id: str
    name: str
    priority: str
    required: bool
    command_env: str


def load_memory_benchmark_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path is not None else REGISTRY_PATH
    with registry_path.open("r", encoding="utf-8") as handle:
        registry = json.load(handle)
    validate_memory_benchmark_registry(registry)
    return registry


def validate_memory_benchmark_registry(registry: dict[str, Any]) -> None:
    benchmark_ids = [item["id"] for item in registry.get("benchmarks", [])]
    comparator_ids = [item["id"] for item in registry.get("comparators", [])]
    if len(benchmark_ids) != len(set(benchmark_ids)):
        raise ValueError("duplicate benchmark ids in memory benchmark registry")
    if len(comparator_ids) != len(set(comparator_ids)):
        raise ValueError("duplicate comparator ids in memory benchmark registry")
    missing_required = sorted(set(registry.get("required_benchmark_ids", [])) - set(benchmark_ids))
    if missing_required:
        raise ValueError(f"required benchmark ids missing from benchmark list: {missing_required}")
    missing_comparators = sorted(set(registry.get("required_comparator_ids", [])) - set(comparator_ids))
    if missing_comparators:
        raise ValueError(f"required comparator ids missing from comparator list: {missing_comparators}")
    for item in registry.get("benchmarks", []):
        if not item.get("command_env"):
            raise ValueError(f"benchmark {item.get('id')} is missing command_env")


def benchmark_plan(scope: str = "required", registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or load_memory_benchmark_registry()
    benchmarks = _select_benchmarks(registry, scope)
    cases = []
    for item in benchmarks:
        env_name = str(item["command_env"])
        command = os.environ.get(env_name)
        cases.append(
            {
                "id": item["id"],
                "name": item["name"],
                "priority": item.get("priority", "P3"),
                "required": bool(item.get("required", False)),
                "command_env": env_name,
                "configured": bool(command),
                "command": command or None,
            }
        )
    return {
        "version": PLAN_VERSION,
        "scope": scope,
        "required_benchmark_ids": registry.get("required_benchmark_ids", []),
        "required_comparator_ids": registry.get("required_comparator_ids", []),
        "benchmarks": cases,
        "comparators": registry.get("comparators", []),
        "summary": {
            "benchmark_count": len(cases),
            "configured_count": sum(1 for case in cases if case["configured"]),
            "missing_required_commands": [case["command_env"] for case in cases if case["required"] and not case["configured"]],
        },
    }


def run_external_memory_benchmarks(
    scope: str = "required",
    strict: bool = False,
    registry: dict[str, Any] | None = None,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    registry = registry or load_memory_benchmark_registry()
    cases = []
    for item in _select_benchmarks(registry, scope):
        command_env = str(item["command_env"])
        command = os.environ.get(command_env)
        if not command:
            status = "NOT_CONFIGURED"
            cases.append(_case_result(item, command_env, status, command=None, returncode=None, stdout="", stderr=""))
            continue
        completed = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        status = "PASS" if completed.returncode == 0 else "FAIL"
        cases.append(
            _case_result(
                item,
                command_env,
                status,
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        )
    strict_failure_statuses = set(registry.get("policy", {}).get("strict_mode_failure_statuses", []))
    failing = [case for case in cases if case["status"] in strict_failure_statuses]
    action_required = [case for case in cases if case["required"] and case["status"] == "NOT_CONFIGURED"]
    status = "PASS"
    if strict and failing:
        status = "FAIL"
    elif action_required:
        status = "ACTION_REQUIRED"
    elif any(case["status"] == "FAIL" for case in cases):
        status = "FAIL"
    return {
        "version": REPORT_VERSION,
        "scope": scope,
        "strict": strict,
        "status": status,
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "pass_count": sum(1 for case in cases if case["status"] == "PASS"),
            "fail_count": sum(1 for case in cases if case["status"] == "FAIL"),
            "not_configured_count": sum(1 for case in cases if case["status"] == "NOT_CONFIGURED"),
            "required_not_configured": [case["id"] for case in action_required],
        },
    }


def render_external_memory_plan_pretty(payload: dict[str, Any]) -> str:
    lines = [
        "SEAM external memory benchmark plan",
        f"Scope: {payload.get('scope')}",
        f"Configured: {payload.get('summary', {}).get('configured_count')}/{payload.get('summary', {}).get('benchmark_count')}",
        "",
        "Benchmarks:",
    ]
    for case in payload.get("benchmarks", []):
        marker = "configured" if case.get("configured") else "missing"
        required = "required" if case.get("required") else "optional"
        lines.append(f"- {case['id']} ({case['name']}): {required}, {marker}, env={case['command_env']}")
    missing = payload.get("summary", {}).get("missing_required_commands", [])
    if missing:
        lines.extend(["", "Missing required runner commands:", *[f"- {env}" for env in missing]])
    return "\n".join(lines)


def render_external_memory_report_pretty(payload: dict[str, Any]) -> str:
    lines = [
        f"SEAM external memory benchmarks: {payload.get('status')}",
        f"Scope: {payload.get('scope')} strict={payload.get('strict')}",
        "",
        "Cases:",
    ]
    for case in payload.get("cases", []):
        lines.append(f"- {case['id']} ({case['name']}): {case['status']} env={case['command_env']}")
    required_missing = payload.get("summary", {}).get("required_not_configured", [])
    if required_missing:
        lines.extend(["", "Required benchmarks without configured runners:", *[f"- {case_id}" for case_id in required_missing]])
    return "\n".join(lines)


def _select_benchmarks(registry: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    benchmarks = list(registry.get("benchmarks", []))
    if scope == "all":
        return benchmarks
    if scope == "required":
        return [item for item in benchmarks if item.get("required")]
    selected = [item for item in benchmarks if item.get("id") == scope]
    if not selected:
        known = ", ".join(item.get("id", "") for item in benchmarks)
        raise ValueError(f"unknown external memory benchmark scope {scope!r}; known: {known}")
    return selected


def _case_result(
    item: dict[str, Any],
    command_env: str,
    status: str,
    command: str | None,
    returncode: int | None,
    stdout: str,
    stderr: str,
) -> dict[str, Any]:
    return {
        "id": item["id"],
        "name": item["name"],
        "priority": item.get("priority", "P3"),
        "required": bool(item.get("required", False)),
        "command_env": command_env,
        "command": command,
        "status": status,
        "returncode": returncode,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }

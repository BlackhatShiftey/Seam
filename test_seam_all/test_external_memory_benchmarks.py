from __future__ import annotations

import shlex
import sys

from seam_runtime.external_memory_benchmarks import benchmark_plan, load_memory_benchmark_registry, run_external_memory_benchmarks


def test_memory_benchmark_registry_contains_required_targets() -> None:
    registry = load_memory_benchmark_registry()
    required = set(registry["required_benchmark_ids"])
    assert {
        "locomo",
        "convomem",
        "membench",
        "longmemeval",
        "beam",
        "perltqa",
        "evermembench",
        "memora",
        "mem2actbench",
    }.issubset(required)
    comparator_ids = {item["id"] for item in registry["comparators"]}
    assert {"mem0", "zep_graphiti", "letta_memgpt", "mempalace", "hindsight", "memmachine"}.issubset(comparator_ids)


def test_external_memory_plan_marks_missing_required_commands() -> None:
    plan = benchmark_plan(scope="required")
    assert plan["summary"]["benchmark_count"] == len(plan["required_benchmark_ids"])
    assert plan["summary"]["missing_required_commands"]


def test_external_memory_runner_can_execute_configured_single_benchmark(monkeypatch) -> None:
    command = f'{shlex.quote(sys.executable)} -c "import sys; sys.exit(0)"'
    monkeypatch.setenv("SEAM_BENCH_LOCOMO_COMMAND", command)
    report = run_external_memory_benchmarks(scope="locomo", strict=True)
    assert report["status"] == "PASS"
    assert report["cases"][0]["status"] == "PASS"


def test_external_memory_runner_strict_mode_fails_on_unconfigured_required(monkeypatch) -> None:
    monkeypatch.delenv("SEAM_BENCH_LOCOMO_COMMAND", raising=False)
    report = run_external_memory_benchmarks(scope="locomo", strict=True)
    assert report["status"] == "FAIL"
    assert report["cases"][0]["status"] == "NOT_CONFIGURED"

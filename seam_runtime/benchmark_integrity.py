from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

BUNDLE_VERSION = "SEAM-BENCHMARK-BUNDLE/1"
INPUT_MANIFEST_VERSION = "SEAM-BENCHMARK-INPUT-MANIFEST/1"
SUPPORTED_BIL_LEVELS = {"BIL-0", "BIL-1", "BIL-2"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json_payload(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return copy.deepcopy(source)
    path = Path(source)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_payload(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def result_hash(result: dict[str, Any]) -> str:
    return sha256_canonical(result)


def build_input_manifest(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("version") == "SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/1":
        cases = result.get("cases") or []
        case_ids = sorted(str(case.get("case_id")) for case in cases if case.get("case_id") is not None)
        judge_entries = [case.get("judge") for case in cases if isinstance(case.get("judge"), dict)]
        judge_names = sorted(
            {str(entry.get("judge_name")) for entry in judge_entries if entry.get("judge_name") is not None}
        )
        judge_models = sorted(
            {str(entry.get("judge_model")) for entry in judge_entries if entry.get("judge_model") is not None}
        )
        return {
            "version": INPUT_MANIFEST_VERSION,
            "benchmark": result.get("benchmark"),
            "adapter": result.get("adapter"),
            "dataset": copy.deepcopy(result.get("dataset") or {}),
            "case_count": len(cases),
            "case_ids": case_ids,
            "judge": {
                "present": bool(judge_entries),
                "judge_names": judge_names,
                "judge_models": judge_models,
            },
        }
    if result.get("version") == "SEAM-BENCH/1":
        families = result.get("families") or {}
        family_cases: dict[str, list[str]] = {}
        for family_name, family in families.items():
            cases = family.get("cases") if isinstance(family, dict) else []
            family_cases[str(family_name)] = sorted(
                str(case.get("case_id") or case.get("id") or case.get("name"))
                for case in cases or []
                if isinstance(case, dict)
            )
        return {
            "version": INPUT_MANIFEST_VERSION,
            "benchmark": "seam-internal",
            "run_id": result.get("run_id"),
            "requested_suite": result.get("requested_suite"),
            "executed_suites": list(result.get("executed_suites") or []),
            "fixture_scope": result.get("fixture_scope"),
            "families": family_cases,
        }
    return {
        "version": INPUT_MANIFEST_VERSION,
        "benchmark": result.get("benchmark") or result.get("version") or "unknown",
        "case_count": len(result.get("cases") or []),
        "case_ids": sorted(
            str(case.get("case_id") or case.get("id"))
            for case in result.get("cases") or []
            if isinstance(case, dict) and (case.get("case_id") or case.get("id"))
        ),
    }


def seal_benchmark_bundle(result: dict[str, Any], *, level: str = "BIL-2") -> dict[str, Any]:
    if level not in SUPPORTED_BIL_LEVELS or level == "BIL-0":
        raise ValueError(f"unsupported BIL level for sealing: {level}")
    result_copy = copy.deepcopy(result)
    manifest = build_input_manifest(result_copy) if level == "BIL-2" else None
    return {
        "version": BUNDLE_VERSION,
        "bil": {
            "level": level,
            "result_hash": result_hash(result_copy),
            "input_manifest_hash": sha256_canonical(manifest) if manifest is not None else None,
        },
        "result": result_copy,
        "input_manifest": manifest,
    }


def verify_benchmark_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    status = "PASS"
    if bundle.get("version") != BUNDLE_VERSION:
        return {
            "version": "SEAM-BENCHMARK-BUNDLE-VERIFY/1",
            "status": "FAIL",
            "bil": {"level": "BIL-0", "sealed": False},
            "checks": [{"id": "bundle_version", "status": "FAIL", "message": "not a SEAM benchmark bundle"}],
        }
    bil = bundle.get("bil") or {}
    level = bil.get("level")
    result = bundle.get("result")
    if level not in {"BIL-1", "BIL-2"}:
        checks.append({"id": "bil_level", "status": "FAIL", "message": f"unsupported level {level!r}"})
    else:
        checks.append({"id": "bil_level", "status": "PASS", "message": ""})
    if not isinstance(result, dict):
        checks.append({"id": "result", "status": "FAIL", "message": "bundle result must be an object"})
    else:
        actual = result_hash(result)
        expected = bil.get("result_hash")
        checks.append({
            "id": "result_hash",
            "status": "PASS" if actual == expected else "FAIL",
            "expected": expected,
            "actual": actual,
            "message": "" if actual == expected else "result hash mismatch",
        })
    if level == "BIL-2":
        manifest = bundle.get("input_manifest")
        if not isinstance(manifest, dict):
            checks.append({"id": "input_manifest", "status": "FAIL", "message": "BIL-2 requires input_manifest object"})
        else:
            actual = sha256_canonical(manifest)
            expected = bil.get("input_manifest_hash")
            checks.append({
                "id": "input_manifest_hash",
                "status": "PASS" if actual == expected else "FAIL",
                "expected": expected,
                "actual": actual,
                "message": "" if actual == expected else "input manifest hash mismatch",
            })
            if isinstance(result, dict):
                derived_manifest = build_input_manifest(result)
                checks.append({
                    "id": "input_manifest_matches_result",
                    "status": "PASS" if manifest == derived_manifest else "FAIL",
                    "expected": sha256_canonical(derived_manifest),
                    "actual": actual,
                    "message": "" if manifest == derived_manifest else "input manifest does not match result",
                })
    for check in checks:
        if check.get("status") != "PASS":
            status = "FAIL"
    return {
        "version": "SEAM-BENCHMARK-BUNDLE-VERIFY/1",
        "status": status,
        "bil": {
            "level": level or "BIL-0",
            "sealed": True,
            "result_hash": bil.get("result_hash"),
            "input_manifest_hash": bil.get("input_manifest_hash"),
        },
        "checks": checks,
    }


def inspect_benchmark_integrity(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("version") == BUNDLE_VERSION:
        verification = verify_benchmark_bundle(payload)
        return {
            "version": "SEAM-BENCHMARK-INTEGRITY-INSPECT/1",
            "status": verification["status"],
            "bil": verification["bil"],
            "verification": verification,
        }
    return {
        "version": "SEAM-BENCHMARK-INTEGRITY-INSPECT/1",
        "status": "PASS",
        "bil": {
            "level": "BIL-0",
            "sealed": False,
            "computed_result_hash": result_hash(payload),
            "input_manifest": build_input_manifest(payload),
        },
        "verification": None,
    }

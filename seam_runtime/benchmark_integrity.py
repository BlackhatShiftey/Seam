from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

BUNDLE_VERSION = "SEAM-BENCHMARK-BUNDLE/1"
INPUT_MANIFEST_VERSION = "SEAM-BENCHMARK-INPUT-MANIFEST/1"
SUPPORTED_BIL_LEVELS = {"BIL-0", "BIL-1", "BIL-2"}
VOLATILE_RESULT_HASH_KEYS = {
    "answer_latency_ms",
    "created_at",
    "elapsed_seconds",
    "retrieval_latency_ms",
    "run_started_at",
}


def _is_external_memory_result(result: dict[str, Any]) -> bool:
    version = result.get("version")
    return isinstance(version, str) and version.startswith("SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/")


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
    return sha256_canonical(stable_result_hash_input(result))


def stable_result_hash_input(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: stable_result_hash_input(item)
            for key, item in value.items()
            if key not in VOLATILE_RESULT_HASH_KEYS
        }
    if isinstance(value, list):
        return [stable_result_hash_input(item) for item in value]
    return copy.deepcopy(value)


def build_input_manifest(result: dict[str, Any]) -> dict[str, Any]:
    if _is_external_memory_result(result):
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


def seal_benchmark_bundle(
    result: dict[str, Any], *, level: str = "BIL-2", allow_stub_seal: bool = False
) -> dict[str, Any]:
    if level not in SUPPORTED_BIL_LEVELS or level == "BIL-0":
        raise ValueError(f"unsupported BIL level for sealing: {level}")
    if level in {"BIL-1", "BIL-2"} and not allow_stub_seal:
        for case in result.get("cases") or []:
            judge = case.get("judge")
            if _is_external_memory_result(result) and not isinstance(judge, dict):
                raise ValueError(
                    "unjudged benchmark result cannot be sealed above BIL-0; "
                    "pass allow_stub_seal=True to override"
                )
            if isinstance(judge, dict) and judge.get("judge_name") in {
                "stub",
                "stub-informational-only",
            }:
                raise ValueError(
                    "stub judge cannot be sealed above BIL-0; "
                    "pass allow_stub_seal=True to override"
                )
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


def validate_publication_readiness(
    result: dict[str, Any],
    *,
    git_sha: str = "",
    fixture_hash: str = "",
    dataset_name: str = "",
    bil_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check whether a benchmark result is ready for competitive publication.

    A result is publication-ready only when ALL of:
    - judge is non-stub
    - dataset name and fixture hash are provided
    - git SHA is provided
    - adapter name is present in the result
    - per-category metrics present (when categories exist in cases)
    - BIL-2 verification passes

    Stub-judge results are REFUSED for publication regardless of BIL level.
    """
    checks: list[dict[str, Any]] = []
    cases = result.get("cases") or []

    # Judge must be non-stub
    judge_names: set[str] = set()
    for case in cases:
        j = case.get("judge")
        if isinstance(j, dict):
            jn = j.get("judge_name", "")
            if jn:
                judge_names.add(jn)
    stub_judge = "stub" in judge_names or "stub-informational-only" in judge_names
    if stub_judge:
        checks.append({
            "id": "judge_non_stub",
            "status": "FAIL",
            "message": "stub judge results cannot be published as competitive claims",
        })
    elif not judge_names:
        checks.append({
            "id": "judge_present",
            "status": "FAIL",
            "message": "no judge present in result; real judge required for publication",
        })
    else:
        checks.append({"id": "judge_non_stub", "status": "PASS", "message": ""})

    # Dataset and fixture hash
    if not dataset_name:
        checks.append({
            "id": "dataset_named",
            "status": "FAIL",
            "message": "dataset name is required for publication",
        })
    else:
        checks.append({"id": "dataset_named", "status": "PASS", "message": ""})
    if not fixture_hash:
        checks.append({
            "id": "fixture_hash_present",
            "status": "FAIL",
            "message": "fixture hash is required for publication",
        })
    else:
        checks.append({"id": "fixture_hash_present", "status": "PASS", "message": ""})

    # Git SHA
    if not git_sha:
        checks.append({
            "id": "git_sha_present",
            "status": "FAIL",
            "message": "git SHA is required for publication",
        })
    else:
        checks.append({"id": "git_sha_present", "status": "PASS", "message": ""})

    # Adapter name
    adapter = result.get("adapter")
    if not adapter:
        checks.append({
            "id": "adapter_named",
            "status": "FAIL",
            "message": "adapter name is required for publication",
        })
    else:
        checks.append({"id": "adapter_named", "status": "PASS", "message": ""})

    # Per-category metrics (when categories present in cases)
    categories_present = {c.get("category") for c in cases if c.get("category")}
    if categories_present:
        per_category_data = (
            result.get("per_category")
            or (result.get("scores") or {}).get("per_category")
            or (result.get("scores") or {}).get("category_breakdown")
        )
        if per_category_data:
            checks.append({"id": "per_category_metrics", "status": "PASS", "message": ""})
        else:
            checks.append({
                "id": "per_category_metrics",
                "status": "WARN",
                "message": (
                    f"cases have categories ({sorted(categories_present)}) but no "
                    f"per-category score aggregation present; runner should compute breakdown"
                ),
            })
    else:
        checks.append({"id": "per_category_metrics", "status": "PASS", "message": "no categories present; skipped"})

    if not isinstance(bil_verification, dict):
        checks.append({
            "id": "bil2_verified",
            "status": "FAIL",
            "message": "passing BIL-2 verification is required for publication",
        })
    else:
        bil = bil_verification.get("bil") if isinstance(bil_verification.get("bil"), dict) else {}
        status = bil_verification.get("status")
        level = bil.get("level")
        if status == "PASS" and level == "BIL-2":
            checks.append({"id": "bil2_verified", "status": "PASS", "message": ""})
        else:
            checks.append({
                "id": "bil2_verified",
                "status": "FAIL",
                "message": f"BIL-2 verification must PASS; got status={status!r}, level={level!r}",
            })

    ready = all(c["status"] in ("PASS", "WARN") for c in checks)
    return {
        "version": "SEAM-PUBLICATION-READINESS/1",
        "ready": ready,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": sum(1 for c in checks if c["status"] == "PASS"),
            "warned": sum(1 for c in checks if c["status"] == "WARN"),
            "failed": sum(1 for c in checks if c["status"] == "FAIL"),
        },
        "publication_blocked_by": [c["id"] for c in checks if c["status"] == "FAIL"],
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

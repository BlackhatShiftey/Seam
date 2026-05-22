from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from seam_runtime.benchmark_integrity import (
    BUNDLE_VERSION,
    build_input_manifest,
    inspect_benchmark_integrity,
    seal_benchmark_bundle,
    sha256_canonical,
    verify_benchmark_bundle,
)


def _external_result() -> dict:
    return {
        "version": "SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/1",
        "benchmark": "locomo",
        "adapter": "seam",
        "dataset": {"source": "quickstart", "case_count": 2},
        "run_started_at": "2026-05-19T00:00:00+00:00",
        "elapsed_seconds": 0.12,
        "scores": {"context_recall_mean": 1.0, "answer_em_mean": 1.0, "answer_f1_mean": 1.0},
        "cases": [
            {
                "case_id": "case-b",
                "category": "synthetic",
                "scores": {"context_recall": 1.0, "answer_em": 1.0, "answer_f1": 1.0},
                "judge": {"verdict": "correct", "score": 1.0, "judge_name": "stub", "judge_model": "stub-1"},
            },
            {
                "case_id": "case-a",
                "category": "synthetic",
                "scores": {"context_recall": 1.0, "answer_em": 1.0, "answer_f1": 1.0},
                "judge": {"verdict": "correct", "score": 1.0, "judge_name": "stub", "judge_model": "stub-1"},
            },
        ],
        "integrity_hash": "existing-runner-hash",
    }


def _external_unjudged_result() -> dict:
    result = _external_result()
    for case in result["cases"]:
        case.pop("judge", None)
    return result


def test_seal_bil2_external_result_has_manifest_and_hashes():
    bundle = seal_benchmark_bundle(_external_result(), level="BIL-2", allow_stub_seal=True)

    assert bundle["version"] == BUNDLE_VERSION
    assert bundle["bil"]["level"] == "BIL-2"
    assert len(bundle["bil"]["result_hash"]) == 64
    assert len(bundle["bil"]["input_manifest_hash"]) == 64
    assert bundle["input_manifest"]["benchmark"] == "locomo"
    assert bundle["input_manifest"]["adapter"] == "seam"
    assert bundle["input_manifest"]["case_ids"] == ["case-a", "case-b"]
    assert bundle["input_manifest"]["judge"]["present"] is True
    assert bundle["input_manifest"]["judge"]["judge_names"] == ["stub"]
    assert bundle["input_manifest"]["judge"]["judge_models"] == ["stub-1"]


def test_external_manifest_preserves_metadata_for_new_result_version():
    result = _external_result()
    result["version"] = "SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/2"

    manifest = build_input_manifest(result)

    assert manifest["benchmark"] == "locomo"
    assert manifest["adapter"] == "seam"
    assert manifest["dataset"] == {"source": "quickstart", "case_count": 2}
    assert manifest["case_ids"] == ["case-a", "case-b"]
    assert manifest["judge"]["present"] is True
    assert manifest["judge"]["judge_names"] == ["stub"]


def test_unjudged_external_result_refuses_bil2_by_default():
    with pytest.raises(ValueError, match="unjudged benchmark result cannot be sealed above BIL-0"):
        seal_benchmark_bundle(_external_unjudged_result(), level="BIL-2")


def test_seal_bil1_has_no_input_manifest_hash():
    bundle = seal_benchmark_bundle(_external_result(), allow_stub_seal=True, level="BIL-1")

    assert bundle["bil"]["level"] == "BIL-1"
    assert len(bundle["bil"]["result_hash"]) == 64
    assert bundle["bil"]["input_manifest_hash"] is None
    assert bundle["input_manifest"] is None


def test_verify_bundle_detects_result_tamper():
    bundle = seal_benchmark_bundle(_external_result(), allow_stub_seal=True, level="BIL-2")
    tampered = copy.deepcopy(bundle)
    tampered["result"]["scores"]["answer_em_mean"] = 0.0

    report = verify_benchmark_bundle(tampered)

    assert report["status"] == "FAIL"
    assert any(check["id"] == "result_hash" and check["status"] == "FAIL" for check in report["checks"])


def test_verify_bundle_detects_manifest_tamper():
    bundle = seal_benchmark_bundle(_external_result(), allow_stub_seal=True, level="BIL-2")
    tampered = copy.deepcopy(bundle)
    tampered["input_manifest"]["case_ids"].append("case-z")

    report = verify_benchmark_bundle(tampered)

    assert report["status"] == "FAIL"
    assert any(check["id"] == "input_manifest_hash" and check["status"] == "FAIL" for check in report["checks"])


def test_verify_bundle_detects_manifest_result_mismatch_even_with_recomputed_hashes():
    bundle = seal_benchmark_bundle(_external_result(), allow_stub_seal=True, level="BIL-2")
    tampered = copy.deepcopy(bundle)
    tampered["result"]["cases"].append({
        "case_id": "case-z",
        "category": "synthetic",
        "scores": {"context_recall": 1.0, "answer_em": 1.0, "answer_f1": 1.0},
    })
    tampered["bil"]["result_hash"] = sha256_canonical(tampered["result"])
    tampered["bil"]["input_manifest_hash"] = sha256_canonical(tampered["input_manifest"])

    report = verify_benchmark_bundle(tampered)

    assert report["status"] == "FAIL"
    assert any(check["id"] == "input_manifest_matches_result" and check["status"] == "FAIL" for check in report["checks"])
    assert build_input_manifest(tampered["result"])["case_ids"] == ["case-a", "case-b", "case-z"]


def test_inspect_raw_result_reports_bil0():
    report = inspect_benchmark_integrity(_external_result())

    assert report["status"] == "PASS"
    assert report["bil"]["level"] == "BIL-0"
    assert report["bil"]["sealed"] is False
    assert len(report["bil"]["computed_result_hash"]) == 64


def test_inspect_bundle_reports_bil2_verified():
    bundle = seal_benchmark_bundle(_external_result(), allow_stub_seal=True, level="BIL-2")

    report = inspect_benchmark_integrity(bundle)

    assert report["status"] == "PASS"
    assert report["bil"]["level"] == "BIL-2"
    assert report["bil"]["sealed"] is True
    assert report["verification"]["status"] == "PASS"


def test_unknown_bil_level_rejected():
    with pytest.raises(ValueError, match="unsupported BIL level"):
        seal_benchmark_bundle(_external_result(), allow_stub_seal=True, level="BIL-3")


def test_cli_bench_seal_verify_inspect_roundtrip(tmp_path):
    result_path = tmp_path / "result.json"
    bundle_path = tmp_path / "bundle.json"
    result_path.write_text(json.dumps(_external_result()), encoding="utf-8")

    seal = subprocess.run(
        [
            sys.executable,
            "-m",
            "seam",
            "bench",
            "seal",
            str(result_path),
            "--level",
            "BIL-2",
            "--output",
            str(bundle_path),
            "--allow-stub-seal",
        ],
        capture_output=True,
        text=True,
    )
    assert seal.returncode == 0, seal.stderr
    assert bundle_path.exists()

    verify = subprocess.run(
        [sys.executable, "-m", "seam", "bench", "verify", str(bundle_path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert verify.returncode == 0, verify.stderr
    verify_payload = json.loads(verify.stdout)
    assert verify_payload["status"] == "PASS"
    assert verify_payload["bil"]["level"] == "BIL-2"

    inspect = subprocess.run(
        [sys.executable, "-m", "seam", "bench", "inspect", str(bundle_path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert inspect.returncode == 0, inspect.stderr
    inspect_payload = json.loads(inspect.stdout)
    assert inspect_payload["bil"]["level"] == "BIL-2"
    assert inspect_payload["verification"]["status"] == "PASS"


def test_cli_bench_verify_fails_on_tampered_bundle(tmp_path):
    bundle = seal_benchmark_bundle(_external_result(), allow_stub_seal=True, level="BIL-2")
    bundle["result"]["cases"][0]["scores"]["answer_f1"] = 0.0
    bundle_path = tmp_path / "tampered.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    verify = subprocess.run(
        [sys.executable, "-m", "seam", "bench", "verify", str(bundle_path), "--format", "json"],
        capture_output=True,
        text=True,
    )

    assert verify.returncode == 1
    payload = json.loads(verify.stdout)
    assert payload["status"] == "FAIL"
    assert any(check["id"] == "result_hash" and check["status"] == "FAIL" for check in payload["checks"])


def test_quickstart_stub_result_can_be_sealed_and_verified(tmp_path):
    result_path = tmp_path / "locomo-result.json"
    bundle_path = tmp_path / "locomo-bundle.json"

    quickstart = subprocess.run(
        [
            sys.executable,
            "-m",
            "seam",
            "bench",
            "external",
            "--quickstart",
            "locomo",
            "--adapter",
            "seam",
            "--judge",
            "stub",
            "--output",
            str(result_path),
        ],
        capture_output=True,
        text=True,
    )
    assert quickstart.returncode == 0, quickstart.stderr

    seal = subprocess.run(
        [
            sys.executable,
            "-m",
            "seam",
            "bench",
            "seal",
            str(result_path),
            "--level",
            "BIL-2",
            "--output",
            str(bundle_path),
            "--allow-stub-seal",
        ],
        capture_output=True,
        text=True,
    )
    assert seal.returncode == 0, seal.stderr

    verify = subprocess.run(
        [sys.executable, "-m", "seam", "bench", "verify", str(bundle_path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert verify.returncode == 0, verify.stderr
    payload = json.loads(verify.stdout)
    assert payload["status"] == "PASS"
    assert payload["bil"]["level"] == "BIL-2"

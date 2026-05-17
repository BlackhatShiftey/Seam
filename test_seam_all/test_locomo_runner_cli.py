from __future__ import annotations

import json
import subprocess
import sys
import time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_quickstart(*, output_path: str | None = None) -> subprocess.CompletedProcess:
    """Run `python -m benchmarks.external.locomo.run --quickstart`, optionally with --output."""
    cmd = [sys.executable, "-m", "benchmarks.external.locomo.run", "--quickstart"]
    if output_path is not None:
        cmd.extend(["--output", output_path])
    return subprocess.run(cmd, capture_output=True, text=True)


def _parse_stdout_json(result: subprocess.CompletedProcess) -> dict:
    """Parse stdout as JSON, failing the current test if parsing fails."""
    assert result.stdout, "stdout is empty"
    data = json.loads(result.stdout)
    assert isinstance(data, dict), f"expected JSON object, got {type(data).__name__}"
    return data


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_quickstart_cli_exits_zero() -> None:
    """`--quickstart` exits with returncode 0 and emits valid JSON on stdout."""
    result = _run_quickstart()
    assert result.returncode == 0, (
        f"expected returncode 0, got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )
    data = _parse_stdout_json(result)
    assert data, "parsed JSON should be non-empty"


def test_quickstart_cli_output_has_integrity_hash() -> None:
    """`--quickstart` output contains a 64-character hex integrity_hash."""
    result = _run_quickstart()
    data = _parse_stdout_json(result)
    ih = data.get("integrity_hash")
    assert isinstance(ih, str), f"integrity_hash should be str, got {type(ih).__name__}"
    assert len(ih) == 64, f"expected 64-char hex, got {len(ih)} chars"
    # Verify it is a valid hex string.
    int(ih, 16)


def test_quickstart_cli_output_version() -> None:
    """`--quickstart` output declares the expected version, benchmark, and adapter."""
    result = _run_quickstart()
    data = _parse_stdout_json(result)

    assert data.get("version") == "SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/1", (
        f"unexpected version: {data.get('version')!r}"
    )
    assert data.get("benchmark") == "locomo", (
        f"unexpected benchmark: {data.get('benchmark')!r}"
    )
    assert data.get("adapter") == "seam", (
        f"unexpected adapter: {data.get('adapter')!r}"
    )


def test_quickstart_cli_output_scores_populated() -> None:
    """`--quickstart` output includes scores and a non-empty cases list."""
    result = _run_quickstart()
    data = _parse_stdout_json(result)

    scores = data.get("scores")
    assert isinstance(scores, dict), f"scores should be dict, got {type(scores).__name__}"

    cr_mean = scores.get("context_recall_mean")
    assert isinstance(cr_mean, (int, float)), (
        f"context_recall_mean should be numeric, got {type(cr_mean).__name__}"
    )

    em_mean = scores.get("answer_em_mean")
    assert isinstance(em_mean, (int, float)), (
        f"answer_em_mean should be numeric, got {type(em_mean).__name__}"
    )

    cases = data.get("cases")
    assert isinstance(cases, list), f"cases should be list, got {type(cases).__name__}"
    assert len(cases) > 0, "cases list should be non-empty"


def test_integrity_hash_stable_across_runs(tmp_path) -> None:
    """Running --quickstart twice produces the same integrity_hash."""
    out_a = str(tmp_path / "run_a.json")
    out_b = str(tmp_path / "run_b.json")

    _run_quickstart(output_path=out_a)
    _run_quickstart(output_path=out_b)

    with open(out_a) as f:
        data_a = json.load(f)
    with open(out_b) as f:
        data_b = json.load(f)

    assert data_a["integrity_hash"] == data_b["integrity_hash"], (
        f"integrity_hash mismatch:\n  run_a: {data_a['integrity_hash']}\n  run_b: {data_b['integrity_hash']}"
    )


def test_quickstart_completes_under_60_seconds() -> None:
    """`--quickstart` completes in under 60 seconds."""
    t0 = time.monotonic()
    result = _run_quickstart()
    elapsed = time.monotonic() - t0

    assert result.returncode == 0, (
        f"expected returncode 0, got {result.returncode}\nstderr: {result.stderr}"
    )
    assert elapsed < 60, (
        f"expected elapsed < 60 s, got {elapsed:.2f} s"
    )

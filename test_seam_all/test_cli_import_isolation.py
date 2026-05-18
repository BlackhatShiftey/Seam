from __future__ import annotations
import os
import subprocess
import sys


def test_seam_doctor_runs_without_retrieval_orchestrator_imported():
    """seam doctor should succeed even when retrieval_orchestrator is not importable."""
    env = os.environ.copy()
    env["SEAM_DB"] = ":memory:"
    result = subprocess.run(
        [sys.executable, "-m", "seam", "doctor"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

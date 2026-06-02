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


def test_dashboard_module_imports_without_retrieval_orchestrator_available():
    """Dashboard module import should not depend on experimental retrieval startup."""
    code = r'''
import importlib.abc
import sys

class BlockRetrievalOrchestrator(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("seam_runtime.retrieval_orchestrator"):
            raise ImportError("blocked for dashboard import isolation test")
        return None

sys.meta_path.insert(0, BlockRetrievalOrchestrator())
import seam_runtime.dashboard
print("dashboard import ok")
'''
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "dashboard import ok" in result.stdout

"""M8 — TestCountFact rename to silence pytest collection warning."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_no_test_class_warning():
    """pytest --collect-only on test_count_audit.py produces no PytestCollectionWarning."""
    target = REPO_ROOT / "tools" / "history" / "test_count_audit.py"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(target)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    combined = result.stdout + result.stderr
    assert "PytestCollectionWarning" not in combined, f"unexpected warning: {combined}"
    assert "cannot collect test class" not in combined, f"unexpected warning: {combined}"
    # exit 0 = tests collected, exit 5 = no tests collected. Both are fine.
    assert result.returncode in (0, 5), f"exit {result.returncode}"

"""H5 — .cursor/ added to .gitignore."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GITIGNORE = REPO_ROOT / ".gitignore"


def test_gitignore_includes_cursor_dir():
    """Parsing .gitignore includes exact-match entry for .cursor/."""
    lines = GITIGNORE.read_text().splitlines()
    patterns = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    assert ".cursor/" in patterns, ".cursor/ not found in .gitignore patterns"

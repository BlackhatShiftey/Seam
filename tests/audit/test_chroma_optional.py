"""chromadb must stay an OPTIONAL extra, never a core dependency.

SEAM defaults to the SQLite vector adapter (and supports pgvector); the Chroma
backend is opt-in and lazy-imported in ``ChromaSemanticAdapter._client``. This
guards against chromadb creeping back into core ``dependencies`` (which would
force the heavy dep on every install).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _project() -> dict:
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]


def test_chromadb_not_in_core_dependencies():
    assert not any("chromadb" in dep for dep in _project()["dependencies"])


def test_chromadb_is_an_optional_extra():
    extras = _project()["optional-dependencies"]
    assert any("chromadb" in dep for dep in extras["chroma"])
    # a full install (all-extras) still pulls it in
    assert any("chromadb" in dep for dep in extras["all-extras"])

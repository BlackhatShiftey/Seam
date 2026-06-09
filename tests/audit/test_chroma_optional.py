"""chromadb must stay an OPT-IN-ONLY extra - never a forced dependency.

chromadb 1.0.0-1.5.9 carries an UNPATCHED critical advisory (GHSA-f4j7-r4q5-qw2c,
pre-auth code injection in the Chroma server). SEAM uses only the embedded
PersistentClient (lazy-imported in ``ChromaSemanticAdapter._client``) and
defaults to the SQLite vector adapter, so chromadb must NOT be pulled by any
default/convenience path: not in core ``dependencies``, not in ``requirements.txt``
(used by the installers/bootstrap), and not in ``all-extras``. It lives ONLY in
the explicit ``chroma`` extra (`seam[chroma]`). These tests guard that.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_PYPROJECT = _REPO / "pyproject.toml"
_REQUIREMENTS = _REPO / "requirements.txt"


def _project() -> dict:
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]


def test_chromadb_not_in_core_dependencies():
    assert not any("chromadb" in dep for dep in _project()["dependencies"])


def test_chromadb_not_in_requirements_txt():
    # requirements.txt is what the installers/bootstrap pip-install; it must not
    # force a vulnerable chromadb (GHSA-f4j7-r4q5-qw2c).
    assert "chromadb" not in _REQUIREMENTS.read_text(encoding="utf-8")


def test_chromadb_only_in_the_explicit_chroma_extra():
    extras = _project()["optional-dependencies"]
    assert any("chromadb" in dep for dep in extras["chroma"])
    # NOT pulled by the convenience "everything" extra (unpatched critical advisory)
    assert not any("chromadb" in dep for dep in extras["all-extras"])

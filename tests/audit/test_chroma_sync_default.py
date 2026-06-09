"""P3 Fix 6 — Chroma sync_on_search default is False.

No chromadb needed here: the adapter is a dataclass and only imports chromadb
lazily in ``_client()`` (on first real use), so constructing it to read the
``sync_on_search`` default works on a core-only install (chromadb is the
optional ``seam[chroma]`` extra).
"""
from __future__ import annotations

from seam_runtime.retrieval_orchestrator.adapters import ChromaSemanticAdapter


def test_default_sync_on_search_is_false() -> None:
    adapter = ChromaSemanticAdapter(store=None, embedding_model=None)
    assert adapter.sync_on_search is False


def test_opt_in_sync_on_search_stores_true() -> None:
    adapter = ChromaSemanticAdapter(store=None, embedding_model=None, sync_on_search=True)
    assert adapter.sync_on_search is True

"""Cross-encoder re-ranker for LoCoMo benchmark retrieval.

A cross-encoder reads (query, candidate) jointly and produces a relevance
score. It is too expensive for full-corpus search but cheap on the top-K
results from the bi-encoder retrieval pass.

Default model: ``cross-encoder/ms-marco-MiniLM-L6-v2`` (384-dim, fast).
Requires ``sentence-transformers`` to be installed.
"""

from __future__ import annotations

from functools import lru_cache


def cross_encoder_rerank(
    query: str,
    candidates: list[str],
    model: str = "cross-encoder/ms-marco-MiniLM-L6-v2",
) -> list[float]:
    """Re-rank candidate texts against a query using a cross-encoder.

    Returns scores in the same order as *candidates*. Higher scores mean
    greater relevance. Raises ``RuntimeError`` when ``sentence_transformers``
    is not installed.
    """
    encoder = _load_cross_encoder(model)
    pairs = [[query, text] for text in candidates]
    scores = encoder.predict(pairs)
    return [float(s) for s in scores]


@lru_cache(maxsize=4)
def _load_cross_encoder(model: str):
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "cross-encoder reranker requires sentence-transformers. "
            "Install with: pip install sentence-transformers"
        ) from exc

    return CrossEncoder(model)


def clear_cross_encoder_cache() -> None:
    _load_cross_encoder.cache_clear()

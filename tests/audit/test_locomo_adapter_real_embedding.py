"""Verify the LoCoMo adapter enforces a real embedding model."""

import pytest


def test_open_runtime_uses_real_embedding(tmp_path):
    """_open_runtime should produce a runtime with a non-hash embedding model."""
    from benchmarks.external.locomo.adapters.seam import _open_runtime

    db_path = tmp_path / "test_real_embed.db"
    rt = _open_runtime(db_path)
    assert not rt.embedding_model.name.startswith("hash"), (
        f"Expected real embedding model, got {rt.embedding_model.name}"
    )


def test_open_runtime_surfaces_missing_sbert(monkeypatch, tmp_path):
    """When SentenceTransformerModel fails, RuntimeError surfaces clear install hint."""
    from benchmarks.external.locomo.adapters.seam import _open_runtime

    def _raise(*args, **kwargs):
        raise ImportError("no sentence_transformers")

    monkeypatch.setattr(
        "seam_runtime.models.SentenceTransformerModel.__init__",
        _raise,
    )
    db_path = tmp_path / "test_missing_sbert.db"
    with pytest.raises(RuntimeError, match="sentence-transformers"):
        _open_runtime(db_path)

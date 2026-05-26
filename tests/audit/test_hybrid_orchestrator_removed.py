from pathlib import Path


def test_legacy_hybrid_orchestrator_package_removed():
    repo_root = Path(__file__).resolve().parents[2]

    assert not (repo_root / "experimental" / "hybrid_orchestrator").exists()


def test_retrieval_orchestrator_keeps_hybrid_aliases():
    from experimental.retrieval_orchestrator import (
        HybridCandidate,
        HybridOrchestrator,
        HybridSearchResult,
        RetrievalCandidate,
        RetrievalOrchestrator,
        RetrievalSearchResult,
    )

    assert HybridOrchestrator is RetrievalOrchestrator
    assert HybridCandidate is RetrievalCandidate
    assert HybridSearchResult is RetrievalSearchResult

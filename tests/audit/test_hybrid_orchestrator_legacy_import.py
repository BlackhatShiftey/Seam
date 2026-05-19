"""Legacy retrieval-orchestrator import path must remain compatible."""


def test_hybrid_orchestrator_package_reexports_retrieval_orchestrator():
    from experimental.hybrid_orchestrator import HybridOrchestrator, RetrievalOrchestrator

    assert HybridOrchestrator is RetrievalOrchestrator


def test_hybrid_orchestrator_submodules_reexport_current_modules():
    from experimental.hybrid_orchestrator.adapters import SQLiteIRAdapter
    from experimental.hybrid_orchestrator.planner import build_plan
    from experimental.hybrid_orchestrator.types import QueryIntent

    assert SQLiteIRAdapter.__name__ == "SQLiteIRAdapter"
    assert callable(build_plan)
    assert QueryIntent.STRUCTURED.value == "structured"

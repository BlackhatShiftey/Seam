# Retrieval Orchestrator (Experimental)

This package is the experimental retrieval-planning layer for SEAM's machine-first memory runtime.

Purpose:

- classify a request as structured, semantic, or mixed retrieval
- build a retrieval plan before search runs
- execute canonical SQLite retrieval plus derived semantic retrieval
- normalize results into a consistent SEAM candidate shape
- merge, rerank, and optionally trace the run for glassbox inspection

Architecture stance:

- SQLite remains the canonical source of truth
- vector indexes, including Chroma, are derived retrieval layers
- retrieval output should stay traceable back to canonical records and exact payloads
- this package is still isolated from `seam_runtime` while we decide its long-term home
- deeper machine-projection integration should only happen after the benchmark engine proves retrieval quality holds up

Current implementation:

- `planner.py` classifies requests and extracts lightweight filters such as `kind:CLM` or `scope:thread`
- `adapters.py` runs a structured SQLite leg and a semantic vector leg against the live SEAM runtime
- the SQLite leg pushes field filters, lexical gating, and ranking into SQL instead of relying on a weak in-memory pass
- `adapters.py` also includes an optional `ChromaSemanticAdapter` for a Chroma-backed semantic leg
- `merger.py` normalizes and reranks merged candidates
- `orchestrator.py` exposes `RetrievalOrchestrator.plan()` and `RetrievalOrchestrator.search()`
- `orchestrator.py` also exposes persistent index syncing plus `rag()` context retrieval that can feed `pack`, `prompt`, `evidence`, `summary`, or exact `records` views

Compatibility:

- the canonical package path is `experimental.retrieval_orchestrator`
- the legacy import path `experimental.hybrid_orchestrator` still resolves
- the legacy class names `HybridOrchestrator`, `HybridSearchResult`, and `HybridCandidate` remain as aliases

Suggested next architecture steps:

1. Decide whether retrieval orchestration folds into `seam_runtime` or remains an experimental package.
2. Evaluate natural, machine, and hybrid retrieval projections with the benchmark engine before changing defaults.
3. Add richer trace spans and latency accounting for retrieval debugging.
4. Keep aligning operator terminology around retrieval, context views, and machine-first persistence.

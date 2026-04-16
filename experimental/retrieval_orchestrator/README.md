# Retrieval Orchestrator (Experimental)

This package is an experimental SEAM extension for retrieval orchestration.

Purpose:
- classify a request as structured, semantic, or mixed retrieval
- build a retrieval plan
- run SQL and vector retrieval legs
- normalize results into a canonical object shape
- merge, rerank, and optionally trace the run

This experimental package is intentionally isolated from the current `seam_runtime` so the repo's existing memory/runtime work remains untouched.

Current implementation:
- `planner.py` classifies requests and extracts lightweight filters such as `kind:CLM` or `scope:thread`
- `adapters.py` runs a structured SQLite leg and a semantic vector leg against the live SEAM runtime
- `adapters.py` also includes an optional `ChromaSemanticAdapter` for a Chroma-backed semantic leg
- `merger.py` normalizes and reranks merged candidates
- `orchestrator.py` exposes `RetrievalOrchestrator.plan()` and `RetrievalOrchestrator.search()`
- `orchestrator.py` also exposes persistent index syncing plus `rag()` context-pack retrieval

Compatibility:
- the legacy import path `experimental.hybrid_orchestrator` still resolves
- the legacy class names `HybridOrchestrator`, `HybridSearchResult`, and `HybridCandidate` remain as aliases

Suggested next wiring steps:
1. Upgrade the SQL leg from in-memory ranking to richer SQLite/Postgres predicates.
2. Connect the semantic leg to external vector stores when needed.
3. Add richer trace spans and latency accounting.
4. Decide whether this package folds into `seam_runtime` or remains an experimental module.

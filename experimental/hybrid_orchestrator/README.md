# Hybrid Orchestrator Scaffold

This package is an experimental SEAM extension for hybrid retrieval orchestration.

Purpose:
- classify a request as structured, semantic, or hybrid
- build a retrieval plan
- run SQL and vector retrieval legs
- normalize results into a canonical object shape
- merge, rerank, and optionally trace the run

This scaffold is intentionally isolated from the current `seam_runtime` so the repo's existing memory/runtime work remains untouched.

Suggested next wiring steps:
1. Connect `SQLAdapter` to SQLite/Postgres.
2. Connect `VectorAdapter` to Chroma/Qdrant/pgvector.
3. Add real cloud/local provider adapters.
4. Add tests for planner, merger, and tracing.
5. Decide whether this package folds into `seam_runtime` or remains an experimental module.

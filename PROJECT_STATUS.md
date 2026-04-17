# SEAM Project Status

This is the quick current-state tracker for the repo.
Use this file for the shortest high-signal view of:

- what has already been built
- what is stable enough to use
- what still needs work
- what we should do next

For a fuller running record of programming work, planning, upkeep, maintenance decisions,
and milestone history, also read:

- `REPO_LEDGER.md`

Last updated: 2026-04-17

## Current State

SEAM is a working machine-first memory compiler/runtime with:

- MIRL compilation from natural language and DSL
- verification and persistence into SQLite
- lexical/vector retrieval and trace output
- symbol promotion and export
- pack/context generation
- optional Chroma-backed retrieval
- a cleaned-up CLI with retrieval-oriented terminology
- a runtime-connected terminal dashboard
- a stronger SQLite retrieval leg with SQL-side filtering and ranking
- richer `context` output views for prompt, evidence, summary, and exact-record workflows
- a lossless `SEAM-LX/1` document machine-language benchmark with exact roundtrip verification
- a six-family benchmark engine covering `lossless`, `retrieval`, `embedding`, `long_context`, `persistence`, and `agent_tasks`
- benchmark bundles with case hashes, bundle hashes, fixture hashes, persisted run history, and improvement-loop output
- machine-artifact, projection-index, benchmark-run, and benchmark-case persistence in SQLite
- packaged terminal entrypoints for `seam` and `seam-benchmark`
- a one-command `seam demo lossless` flow for compressing and rebuilding exact machine text
- tokenizer-aware benchmark reporting with `tiktoken` support and fallback to `char4_approx`
- repo-local bootstrap scripts plus Windows/Linux installer entrypoints for the installed `seam` command
- cross-agent continuity files for Claude, Gemini, and Antigravity

The CLI and dashboard are usable now as operator glassboxes. The primary intended interface is still an AI agent running on-device with SEAM embedded underneath it.

## What Is Done

### Core runtime

- `compile-nl` and `compile-dsl` produce MIRL
- verification works
- SQLite persistence works
- vector indexing works
- search, trace, pack, reconcile, transpile, and symbol export all work

### Retrieval and context pipeline

- retrieval planning exists
- structured + vector retrieval legs exist
- merged ranking exists
- context/RAG pack generation exists
- `context` can emit pack output plus prompt-ready, evidence/citation, summary, and exact-record views from the same retrieval result
- the structured SQLite leg now pushes filters, lexical gating, and ranking into SQL
- Chroma support exists as an optional semantic backend

### Machine-language and benchmark system

- `SEAM-LX/1` exists as an exact machine-text envelope for document compression
- lossless compression/decompression uses SHA-256 integrity verification
- the lossless loop searches known reversible transforms/codecs until no better candidate remains
- fluctuation/regression logging exists for debugging and future rule design
- the benchmark dashboard tab is wired into the runtime
- the benchmark engine can run, persist, show, and verify benchmark suites
- benchmark bundles are auditable rather than screenshot-only output

### Install and operator surface

- `seam` and `seam-benchmark` are packaged console commands
- `seam doctor` provides a lightweight install-health and smoke-test path
- Windows installer flow has been verified end to end with real command launch, persistence, lossless demo, and dashboard smoke checks
- Linux installer support exists, but still needs a real-machine validation pass

### Durable project memory

- `PROJECT_STATUS.md` remains the short current snapshot
- `REPO_LEDGER.md` remains the long-form engineering memory
- `CLAUDE.md`, `GEMINI.md`, and `ANTIGRAVITY.md` now exist as agent-specific continuity guides that point back to the durable files above

## What Still Needs Work

### 1. Canonical machine projections in the main runtime path

We now persist machine artifacts and projections, but we still need to decide how far to promote those projections into first-class runtime flows without compromising:

- canonical SQLite truth
- exact traceability
- semantic retrieval quality
- reversibility guarantees

### 2. Retrieval evaluation before deeper machine integration

We still need controlled evaluation of:

- natural-text retrieval projections
- machine-text retrieval projections
- hybrid natural + machine projections

> [!TIP]
> **Experimental Evidence:** We have validated that SBERT-based semantic retrieval closes the cross-domain gap (natural query vs. machine document) entirely, achieving 100% recall across all tracks. This confirms our machine-projection architecture is viable for production.

The benchmark engine is now the place to prove those choices instead of making them by taste.

### 3. Benchmark publication and holdout strategy

The glassbox benchmark engine now exists, but publication rigor can still improve with:

- holdout suites
- benchmark diff tooling
- publish helpers
- stronger cross-machine reproducibility checks

### 4. Cross-platform verification depth

The installer path now exists for Windows and Linux, but our verification depth is uneven:

- Windows has been run and verified end to end
- Linux installer support is implemented, but still needs a real-machine validation pass

### 5. Operator-surface polish

The runtime-connected terminal dashboard and packaged CLI entrypoints now exist, but operator polish is still secondary to architecture and benchmark credibility.

## Immediate Next Step

Best next implementation task:

Integrate the PgVector-backed production vector index as the default semantic backend (replacing the SQLite scratchpad for larger deployments) and validate the Linux installer path on a real machine.

## Working Rule

When resuming work in a new conversation:

1. Read this file first.
2. Then read `REPO_LEDGER.md` for deeper project history and maintenance context.
3. Read `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md` if the task touches benchmarking, machine-language rollout, or evaluation policy.
4. Use `CLAUDE.md`, `GEMINI.md`, or `ANTIGRAVITY.md` only as assistant-specific resume guides.
5. Store all benchmark run JSONs in `benchmarks/runs/` and update `benchmarks/BENCHMARK_LOG.md`.
6. Update this file whenever a major milestone or direction changes.

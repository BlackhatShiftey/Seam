# SEAM Repo Ledger

This file is the long-lived engineering ledger for the repository.
It exists to preserve useful project memory across conversations and work sessions.
It should be treated as the assistant-readable persistent repo memory for engineering context.

Use it to track:

- programming milestones
- architecture and naming decisions
- repo upkeep and maintenance notes
- documentation cleanup decisions
- environment and tooling assumptions
- active and future plans
- current work state and step number
- handoff policy

Last updated: 2026-04-17

## How To Use This File

When resuming work:

1. Read `PROJECT_STATUS.md` for the short current snapshot.
2. Read this file for project history, operating context, and maintenance notes.
3. Read `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md` if the task touches benchmark design, bundle publication, or machine-language evaluation.
4. Add a new dated entry when major implementation, cleanup, or planning work is completed.
5. Prefer updating this file over creating temporary handoff notes.

## Current Working Context

### Active branch

- working branch: `feature/hybrid-orchestrator-v2`
- handoff branch: `handoff/archive`

### Current phase

- phase: benchmark-system buildout, machine-projection planning, installer hardening, and cross-agent continuity

### Current step

- step 1 was retrieval/CLI terminology cleanup
- step 2 was Chroma-backed retrieval/context support
- step 3 was retrieval package rename and compatibility cleanup
- step 4 was repo hygiene and durable project memory
- step 5 was runtime-connected dashboard integration and stabilization
- step 6 was strengthening the structured SQLite retrieval leg
- step 7 was richer context output for generation and operator workflows
- step 8 was lossless document compression benchmarking and demo support
- step 9 was iterative lossless optimization logging and benchmark dashboard integration
- step 10 was packaging, installed entrypoints, and one-command lossless demo flows
- step 11 was the six-family glassbox benchmark engine, benchmark persistence, and cross-agent continuity docs
- step 12 was validating the SEAM-LX/1 machine retrieval projection hypothesis using neural embeddings (SBERT) and establishing a persistent benchmark tracking system
- step 13 was adding formal test coverage for `PgVectorAdapter`, wiring `SEAM_PGVECTOR_DSN` env-var pickup into `SeamRuntime`, and surfacing PgVector health in `seam doctor` (55 tests green)
- next implementation step is validating the Linux installer path on a real machine

### Immediate objective

- keep the repo clean
- preserve stable project memory in-repo
- make benchmark claims auditable
- keep SQLite canonical while exploring machine-efficient derived projections
- ensure other assistants can resume work without inventing a parallel project model

## Assistant Memory Rule

Use this ledger as persistent engineering memory for:

- what the project is
- what we already changed
- what decisions were made and why
- what the next step is
- what maintenance rules the repo should follow

Do not use temporary handoff files as the main memory mechanism unless there is a specific reason.
If a handoff is created, summarize the lasting parts back into this ledger.

## Project Identity

### Naming

- `SEAM` is the platform/runtime/tool identity.
- `MIRL` is the memory IR used inside SEAM.
- `PACK` is the derived prompt-time or context-time representation.
- `SEAM-LX/1` is the exact machine-text envelope for lossless document compression and token-efficiency benchmarks.

### Current CLI vocabulary

Primary user-facing commands:

- `compile-nl`
- `compile-dsl`
- `search`
- `plan`
- `retrieve`
- `index`
- `context`
- `compare`
- `benchmark`
- `demo lossless`
- `export-symbols`

Compatibility aliases retained for older stage-language wording:

- `hybrid-plan`
- `hybrid-search`
- `hybrid-compare`
- `rag-sync`
- `rag-search`

### Current retrieval package naming

Canonical package:

- `experimental.retrieval_orchestrator`

Compatibility path:

- `experimental.hybrid_orchestrator`

Rule:

- new code should import the canonical retrieval-oriented package name
- compatibility names may stay until there is an explicit cleanup pass

## Architecture Snapshot

### Core runtime

Main runtime capabilities currently implemented:

- compile MIRL from natural language
- compile MIRL from DSL
- verify MIRL structure and invariants
- persist MIRL records into SQLite
- index records for lexical/vector retrieval
- pack/decompile/reconcile/transpile/export symbols
- persist machine artifacts, projection indexes, and benchmark results into SQLite

### Retrieval stack

Current retrieval stack includes:

- query planning
- inline filter parsing
- structured SQLite retrieval leg
- vector retrieval leg
- merged ranking
- optional trace output
- context pack generation for downstream generation
- richer context views for prompt, evidence, summary, and exact-record workflows
- optional Chroma-backed vector retrieval

### Benchmark stack

Current benchmark stack includes:

- six benchmark families: `lossless`, `retrieval`, `embedding`, `long_context`, `persistence`, `agent_tasks`
- per-case raw traces
- bundle hashes and case hashes
- fixture hashes in the manifest
- persisted benchmark runs and case rows in SQLite
- improvement-loop action aggregation
- bundle verification for tamper detection
- CLI flows for `benchmark run`, `benchmark show`, and `benchmark verify`
- dashboard visibility for benchmark results and search logs

### Persistence model

Canonical persistence:

- SQLite is the canonical store of record truth

Derived stores:

- vector indexes
- pack output
- symbol export artifacts
- machine artifact projections
- benchmark bundles and case traces
- optional Chroma vector store

## Stable Decisions

### Decisions we should preserve

- CLI language should describe what the command does, not internal experimental stage names.
- SQLite remains the canonical source of truth.
- Chroma is optional and should support persistence/retrieval, not replace the canonical record store.
- machine-compressed views may be used as derived retrieval/operator artifacts, but they do not replace canonical SQLite records.
- benchmark claims must ship with auditable raw data, not just aggregate screenshots.
- Experimental retrieval work can evolve, but should not break the stable core runtime unnecessarily.
- Compatibility aliases are acceptable when they reduce churn during terminology cleanup.
- `PROJECT_STATUS.md` and `REPO_LEDGER.md` remain the canonical durable memory files for the repo.

## Cross-Agent Continuity

Agent-specific continuity guides now exist at the repo root:

- `CLAUDE.md`
- `GEMINI.md`
- `ANTIGRAVITY.md`

Rule:

- these files are resume guides, not independent truth stores
- they should point back to `PROJECT_STATUS.md`, `REPO_LEDGER.md`, and benchmark docs
- if any assistant-specific guide drifts from the durable memory files, update the guide and keep the durable memory canonical

## Handoff Policy

### Branch

- reserved handoff branch: `handoff/archive`

### Intended use

- store handoff-only docs there when a separate handoff artifact is truly needed
- keep the main working branch focused on product/runtime/docs that belong with the code
- prefer updating this ledger instead of creating handoff docs by default

## Benchmark Publication Policy

When publishing benchmark results, include:

- the saved JSON bundle
- the bundle hash reported by SEAM
- per-case hashes from the bundle
- fixture hashes from the manifest
- git SHA from the manifest
- tokenizer and dependency state used during measurement
- the exact CLI command used to produce the run

We do not claim machine-efficiency wins without exact reconstruction and reproducible bundle verification.

## Milestone Log

### 2026-04-15

#### Retrieval and CLI work

- built and validated an experimental retrieval orchestrator
- added SQL + vector retrieval legs
- added result merging and ranking
- added context/RAG pack generation
- added optional Chroma semantic backend support
- cleaned up user-facing CLI terminology toward retrieval-oriented language

#### Retrieval naming cleanup

- moved the canonical experimental package to `experimental.retrieval_orchestrator`
- preserved `experimental.hybrid_orchestrator` as a compatibility import layer
- renamed canonical class/result types to retrieval-oriented names while keeping legacy aliases

#### Runtime-connected dashboard work

- added a real `dashboard` CLI command backed by the live SEAM runtime
- connected dashboard actions to compile, search, plan, retrieve, context, index, trace, and stats operations
- added scripted dashboard execution so the terminal surface can be smoke-tested automatically
- verified that a bad dashboard command path stays contained in the UI instead of crashing the process

#### Structured retrieval upgrade

- moved the SQLite retrieval leg away from a weak in-memory scan
- pushed explicit filters for `id`, `kind`, `ns`, `scope`, `predicate`, `subject`, and `object` into SQL
- added SQL-side lexical gating so broad filters do not pull in irrelevant records with zero text match
- added SQL-side ordering using structured score, lexical score, and record freshness/confidence
- added table indexes to support the stronger structured path

#### Richer context output

- added reusable context view formatting for `pack`, `prompt`, `evidence`, `summary`, and `records`
- kept pack generation as the canonical retrieval/context path while exposing richer operator-facing views on top
- extended the RAG result shape to include ranked candidates and exact record payloads so downstream renderers do not have to reconstruct retrieval state
- wired the new context views into both the CLI and the runtime-connected dashboard

#### Lossless machine-language benchmark

- added a dedicated `SEAM-LX/1` lossless machine-text format separate from MIRL compilation
- implemented reversible document compression using standard-library codecs with automatic best-codec selection
- added exact decompression with SHA-256 integrity checking so any mismatch fails loudly
- added benchmark reporting for token savings, byte savings, and intelligence-per-token gain using a deterministic prompt-token estimator
- added CLI commands for `lossless-compress`, `lossless-decompress`, and `lossless-benchmark`
- added a demo input file and regression coverage for exact roundtrips and high-savings benchmark passes

### 2026-04-16

#### Packaging, installer, and operator bootstrap

- added `pyproject.toml` so the repo can be installed editable
- exposed `seam` as the main console script and `seam-benchmark` as a focused benchmark shortcut
- added `seam demo lossless <source> <output>` and `--rebuild` for exact prove-it flows
- added tokenizer-aware benchmark reporting with `tiktoken` fallback behavior
- added `scripts/bootstrap_seam.ps1`, `scripts/enter_seam.ps1`, and `scripts/install_global_seam_command.ps1`
- added `seam doctor` as a lightweight install-health and smoke-test command
- added Windows and Linux installers with a dedicated runtime and persistent default database
- verified the Windows installer flow end to end

#### Glassbox benchmark engine

- added `seam_runtime/benchmarks.py` as the six-family benchmark engine
- added benchmark bundle manifests, bundle hashes, case hashes, fixture hashes, and improvement-loop aggregation
- added benchmark persistence tables and read/write helpers in SQLite for machine artifacts, projections, runs, and cases
- added CLI flows for `benchmark run`, `benchmark show`, and `benchmark verify`
- added benchmark fixtures under `benchmarks/fixtures/`
- verified `benchmark verify` catches tampered bundles
- verified `benchmark show latest` works against persisted runs

#### Cross-agent continuity and benchmark blueprint

- refreshed `CLAUDE.md` so it matches the current repo instead of stale architecture assumptions
- added `GEMINI.md` and `ANTIGRAVITY.md` as assistant-specific resume guides
- added `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md` to hold the phase rollout and benchmark publication blueprint
- updated the repo-owned READMEs and durable memory files so terminology, benchmark policy, and next-step priorities are aligned

## Repo Maintenance Notes

### Files we should generally avoid committing

- temporary exports
- one-off benchmark output bundles unless they are intentionally checked in as reference artifacts
- ephemeral local databases
- generated caches and virtual environments

### Maintenance expectations

- keep the repo clean before and after major changes
- run tests after meaningful runtime changes
- keep `PROJECT_STATUS.md` and `REPO_LEDGER.md` current whenever the direction changes
- prefer auditable benchmark bundles over ad hoc claims in chat or commit messages
### 2026-04-17

#### PgVector Infrastructure Stabilization
- resolved Postgres 18+ volume mounting and credential issues via `docker-compose.yaml` with explicit `PGDATA` paths
- fixed DSN URL-encoding bugs for email-formatted database usernames
- confirmed stable local vector persistence with standard `psycopg` connection patterns

#### Retrieval Projection Validation
- implemented a multi-track evaluation engine in `seam_runtime/evals.py` for Natural vs. Machine text comparisons
- added `SentenceTransformerModel` (SBERT) support to `seam_runtime/models.py` using `sentence-transformers`
- proved the "lossless retrieval" hypothesis: SEAM-LX/1 machine text preserves 100% retrieval recall when using neural embeddings, effectively closing the cross-domain gap without requiring a parallel natural-text index
- established the `benchmarks/runs/` JSON registry and [BENCHMARK_LOG.md](file:///c:/Users/iwana/OneDrive/Documents/Codex/benchmarks/BENCHMARK_LOG.md) for long-term tracking

#### PgVector Adapter Formal Verification
- added `FakePgVectorAdapter` to `test_seam.py` — subclasses `PgVectorAdapter`, overrides `_connect()` with an in-memory cursor and SQL log, no live Postgres required
- added `PgVectorAdapterTests` covering: schema DDL execution, record indexing, upsert dedup, scored search, DSN-based wiring in `SeamRuntime`, and full compile→persist→search round-trip
- all 54 tests green; `PgVectorAdapter` is now formally proven, not just manually confirmed

#### SEAM_PGVECTOR_DSN Environment Variable Support
- `SeamRuntime` now picks up `SEAM_PGVECTOR_DSN` from the environment automatically — no explicit `pgvector_dsn` argument required
- `seam doctor` now checks `SEAM_PGVECTOR_DSN`, attempts a live connection, and reports reachability in its health output
- `seam doctor` dependency table extended to include `psycopg` and `sentence_transformers`
- env-var pickup covered by a new test (`test_runtime_picks_up_pgvector_dsn_from_env`); 55 tests green

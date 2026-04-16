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

Last updated: 2026-04-15

## How To Use This File

When resuming work:

1. Read `PROJECT_STATUS.md` for the short current snapshot.
2. Read this file for project history, operating context, and maintenance notes.
3. Add a new dated entry when major implementation, cleanup, or planning work is completed.
4. Prefer updating this file over creating temporary handoff notes.

Why this is split from `PROJECT_STATUS.md`:

- `PROJECT_STATUS.md` stays short and fast to scan
- this ledger stores the fuller operating memory, rationale, and history

## Current Working Context

### Active branch

- working branch: `feature/hybrid-orchestrator-v2`
- handoff branch: `handoff/archive`

### Current phase

- phase: retrieval/runtime strengthening, dashboard integration, and repo cleanup

### Current step

- step 1 was retrieval/CLI terminology cleanup
- step 2 was Chroma-backed retrieval/context support
- step 3 was retrieval package rename and compatibility cleanup
- step 4 was repo hygiene and durable project memory
- step 5 is runtime-connected dashboard integration and stabilization
- step 6 was strengthening the structured SQLite retrieval leg
- next implementation step is richer context output for generation and operator workflows

### Immediate objective

- keep the repo clean
- preserve stable project memory in-repo
- move next into better SQL filtering/ranking

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

### Retrieval stack

Current retrieval stack includes:

- query planning
- inline filter parsing
- structured SQLite retrieval leg
- vector retrieval leg
- merged ranking
- optional trace output
- context pack generation for downstream generation
- optional Chroma-backed vector retrieval

### Persistence model

Canonical persistence:

- SQLite is the canonical store of record truth

Derived stores:

- vector indexes
- pack output
- symbol export artifacts
- optional Chroma vector store

## Stable Decisions

### Decisions we should preserve

- CLI language should describe what the command does, not internal experimental stage names.
- SQLite remains the canonical source of truth.
- Chroma is optional and should support persistence/retrieval, not replace the canonical record store.
- Experimental retrieval work can evolve, but should not break the stable core runtime unnecessarily.
- Compatibility aliases are acceptable when they reduce churn during terminology cleanup.

### Design decisions already made

- `compile` is the right verb for MIRL creation.
- `export` is the right verb for artifacts like symbol nursery output.
- `index` is clearer than `rag-sync`.
- `context` is clearer than `rag-search`.
- `retrieve` is clearer than `hybrid-search`.

## Architecture Decision Log

### Runtime and persistence

- SQLite is the canonical source of record truth.
- vector systems are retrieval accelerators and derived stores, not the canonical record system.
- Chroma is optional and should complement SQLite rather than replace it.
- context generation should be driven from persisted records and packs, not ad hoc prompt-only state.

### Retrieval structure

- retrieval should be described in user-facing language, not experimental stage language
- explicit filters should be handled structurally before vector fallback whenever practical
- compatibility aliases are acceptable while terminology settles

### Repo memory and documentation

- stable repo memory should live in durable repo files, not temporary conversation handoffs
- `PROJECT_STATUS.md` is the quick snapshot
- `REPO_LEDGER.md` is the long-form engineering memory
- temporary export files and chat-era handoffs should not live in the main repo history unless intentionally preserved

## Handoff Policy

### Branch

- reserved handoff branch: `handoff/archive`

### Intended use

- store handoff-only docs there when a separate handoff artifact is truly needed
- keep the main working branch focused on product/runtime/docs that belong with the code
- prefer updating this ledger instead of creating handoff docs by default

### Rule

- if a future handoff is written, it should either:
  - live only on `handoff/archive`, or
  - be folded into this ledger if it contains lasting engineering value

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

#### Environment and dependency work

- documented and verified local virtual environment setup
- installed and validated `chromadb`
- added `rich` for terminal prototype work

#### Branding/prototype work

- created a retro terminal-style SEAM visual prototype
- built both browser and terminal preview surfaces
- treated this as prototype/design work, not shipped runtime product work

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
- added regression tests to prove irrelevant kind-only matches are excluded and exact structured matches work without free-text terms

#### Documentation and cleanup

- removed temporary handoff files from the repo
- removed generated NotebookLM export artifacts from the repo
- checked for conversation/share links in the repo and found none

## Repo Maintenance Notes

### Files we should generally avoid committing

- temporary exports
- NotebookLM bundles
- generated PDFs
- local screenshots unless intentionally part of product assets
- local databases created by tests or experiments
- one-off conversation handoff files

### Current ignore expectations

The repo should ignore at least:

- `__pycache__/`
- `*.pyc`
- `*.pyo`
- `*.db`
- `.seam_chroma/`
- `exports/`

### Documentation philosophy

Keep:

- stable specs
- implementation docs
- operational docs that help future engineering work
- design rationale that affects code or product direction

Avoid:

- temporary chat handoffs
- export bundles
- duplicated docs that only restate another file
- stale docs that use obsolete naming without purpose

## Active Technical Debt

### Highest-priority runtime debt

1. Context output formats are not rich enough yet.
2. Retrieval still needs a long-term home decision between `experimental/` and `seam_runtime`.
3. Remaining doc language should be aligned around current command vocabulary.

### Lower-priority but useful work

1. Improve and productize the new runtime-connected dashboard surface.
2. Improve trace output with stronger debugging and explainability.
3. Add more durable maintenance scripts if repo workflows get heavier.

## Next Planned Work

### Immediate next step

Add richer `context` output modes so the system can emit prompt text, evidence/citations, summary views, and exact record payloads from the same retrieval result.

### Candidate follow-ups after that

1. Decide whether retrieval should move into `seam_runtime`.
2. Continue terminology/documentation cleanup across the remaining docs.
3. Keep improving and productizing the runtime-connected dashboard surface.

## Update Template

When adding a new project entry, use this structure:

### YYYY-MM-DD

#### What changed

- ...

#### Why it mattered

- ...

#### Follow-up

- ...

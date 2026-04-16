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

Last updated: 2026-04-16

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

- phase: retrieval/runtime strengthening, dashboard integration, packaging, and operator-demo productization

### Current step

- step 1 was retrieval/CLI terminology cleanup
- step 2 was Chroma-backed retrieval/context support
- step 3 was retrieval package rename and compatibility cleanup
- step 4 was repo hygiene and durable project memory
- step 5 is runtime-connected dashboard integration and stabilization
- step 6 was strengthening the structured SQLite retrieval leg
- step 7 was richer context output for generation and operator workflows
- step 8 is lossless document compression benchmarking and demo support
- step 9 is iterative lossless optimization logging and benchmark dashboard integration
- step 10 is packaging, installed entrypoints, and one-command lossless demo flows
- next implementation step is deciding the long-term home of retrieval and how lossless machine text should relate to MIRL/runtime workflows

### Immediate objective

- keep the repo clean
- preserve stable project memory in-repo
- continue promoting retrieval/context into a more polished runtime surface

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
- richer context views for prompt, evidence, summary, and exact-record workflows
- optional Chroma-backed vector retrieval

Current lossless compression surface includes:

- `SEAM-LX/1` machine-text envelope
- exact document compression/decompression
- SHA-256 integrity verification
- benchmark reporting for token savings and exact roundtrip recovery
- iterative search across known reversible transforms/codecs until no better candidate remains
- fluctuation/regression logging for debugging and future rule design
- dashboard benchmark tab with in-memory roundtrip via `decompress-last`
- packaged terminal commands via editable install
- tokenizer-aware benchmark reporting with `tiktoken` fallback behavior
- one-command demo flow via `seam demo lossless` and exact rebuild via `--rebuild`

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
- machine-compressed views may be used as derived retrieval/operator artifacts, but they do not replace canonical SQLite records.
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

#### Richer context output

- added reusable context view formatting for `pack`, `prompt`, `evidence`, `summary`, and `records`
- kept pack generation as the canonical retrieval/context path while exposing richer operator-facing views on top
- extended the RAG result shape to include ranked candidates and exact record payloads so downstream renderers do not have to reconstruct retrieval state
- wired the new context views into both the CLI and the runtime-connected dashboard
- added regression coverage for prompt view, evidence/citation JSON, and exact-record output

#### Lossless machine-language benchmark

- added a dedicated `SEAM-LX/1` lossless machine-text format separate from MIRL compilation
- implemented reversible document compression using standard-library codecs with automatic best-codec selection
- added exact decompression with SHA-256 integrity checking so any mismatch fails loudly
- added benchmark reporting for token savings, byte savings, and intelligence-per-token gain using a deterministic prompt-token estimator
- added CLI commands for `lossless-compress`, `lossless-decompress`, and `lossless-benchmark`
- added a demo input file and regression coverage for exact roundtrips and high-savings benchmark passes

#### Iterative benchmark loop and dashboard benchmark tab

- upgraded the lossless benchmark from a one-shot codec pick into an iterative search over known reversible transforms and codecs
- added per-attempt search logging with regression/fluctuation flags so compression changes can be debugged and used to guide future rule additions
- wired benchmark, compression, decompression, and in-memory `decompress-last` flows into the terminal dashboard
- added a dedicated benchmark tab in the dashboard with benchmark summary and search-log panels

#### Documentation and cleanup

- removed temporary handoff files from the repo
- removed generated NotebookLM export artifacts from the repo
- checked for conversation/share links in the repo and found none

### 2026-04-16

#### Packaging and terminal entrypoints

- added `pyproject.toml` so the repo can be installed editable
- exposed `seam` as the main console script and `seam-benchmark` as a focused benchmark shortcut
- aligned dependency metadata so the packaged operator surface installs `rich`, `chromadb`, and `tiktoken`

#### One-command lossless demo

- added `seam demo lossless <source> <output>` as the main operator-facing prove-it workflow
- added `seam demo lossless <machine> <output> --rebuild` for exact reconstruction from machine text
- kept the lower-level `lossless-compress`, `lossless-decompress`, and `lossless-benchmark` commands intact underneath the demo flow

#### Tokenizer-aware benchmark reporting

- upgraded the lossless benchmark to support tokenizer selection
- added `tiktoken`-backed counting with graceful fallback to `char4_approx`
- threaded tokenizer selection into the CLI and dashboard benchmark surface

#### Verification and coverage

- added regression tests for the new demo compression/rebuild workflow
- added regression coverage for explicit tokenizer selection in the lossless benchmark
- fixed byte-preserving file I/O for the lossless demo path so Windows newline translation does not corrupt rebuild verification

#### Launch UX and operator bootstrap

- added `scripts/bootstrap_seam.ps1` to create `.venv`, install SEAM in editable mode, verify entrypoints, and run a smoke check
- added `scripts/enter_seam.ps1` as a repo-local shell helper so operators can activate the venv and immediately type `seam`
- added `scripts/install_global_seam_command.ps1` so SEAM can install user-level command shims into a PATH location outside the repo venv
- added `seam doctor` as a lightweight install-health and smoke-test command
- updated README so the shortest path to a working `seam` command is explicit, including no-activation usage in new shells

#### Cross-platform installer and persistence setup

- added dedicated installer entrypoints under `installers/` for Windows and Linux
- installer now creates a dedicated SEAM runtime under the user home directory instead of relying on the repo-local development venv
- installer-generated shims set `SEAM_DB_PATH` automatically so `seam` defaults to a durable persistent database
- default installer persistence path is `%LOCALAPPDATA%\SEAM\state\seam.db` on Windows and `~/.local/share/seam/state/seam.db` on Linux
- added `installers/README.md` so the direct platform install commands live beside the installer entrypoints
- updated the repo-owned READMEs to use the current machine-first, glassbox, retrieval/context terminology
- verified the Windows installer flow end to end: installed `seam`, ran `seam doctor`, persisted data into the default runtime database, ran the lossless demo flow, and launched dashboard snapshots from the installed command
- Linux installer support is implemented in the same installer core, but still needs a real Linux validation pass before we can claim field verification

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

1. Retrieval still needs a long-term home decision between `experimental/` and `seam_runtime`.
2. We still need to decide how the lossless machine-language path should integrate with MIRL, packs, and downstream reasoning workflows.
3. We need a canonical machine-projection storage strategy before pushing SEAM-compressed views deeper into derived retrieval systems like Chroma.
4. The iterative lossless optimizer currently searches a small rule set; stronger reversible rules and corpus-driven tuning are the next leverage point.
5. Remaining doc language should be aligned around current command vocabulary.
6. The dashboard/operator surface still needs productization beyond early utility.

### Lower-priority but useful work

1. Improve and productize the new runtime-connected dashboard surface.
2. Improve trace output with stronger debugging and explainability.
3. Add more durable maintenance scripts if repo workflows get heavier.

## Next Planned Work

### Immediate next step

Decide whether retrieval should move into `seam_runtime`, then add a canonical machine-projection layer plus retrieval evaluation so SEAM-compressed derived views can be compared safely against the current semantic-text path before changing Chroma behavior.

### Candidate follow-ups after that

1. Decide whether retrieval should move into `seam_runtime`.
2. Add canonical machine-projection storage for exact SEAM-compressed artifacts.
3. Run retrieval evals for human-readable vs machine-projected vs hybrid semantic indexing.
4. Continue terminology/documentation cleanup across the remaining docs.
5. Keep improving and productizing the runtime-connected dashboard surface.

## Update Template

When adding a new project entry, use this structure:

### YYYY-MM-DD

#### What changed

- ...

#### Why it mattered

- ...

#### Follow-up

- ...

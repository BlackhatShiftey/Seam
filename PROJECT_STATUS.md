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

Last updated: 2026-04-15

## Current State

SEAM is a working memory-first compiler/runtime with:

- MIRL compilation from natural language and DSL
- verification and persistence into SQLite
- lexical/vector retrieval
- symbol promotion and export
- pack/context generation
- Chroma-backed vector retrieval as an option
- a cleaned-up CLI with retrieval-oriented terminology
- a runtime-connected terminal dashboard
- a stronger SQLite retrieval leg with SQL-side filtering and ranking

The CLI is usable now, but not "finished" in the sense of product polish. Core flows work. The biggest remaining runtime gaps are richer context output and deciding where retrieval should live long-term.

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
- the SQLite retrieval leg now pushes field filters, lexical gating, and ordering into SQL instead of relying on a weak in-memory pass
- merged ranking exists
- context/RAG pack generation exists
- Chroma support exists as an optional vector backend

### CLI language cleanup

Primary command language now centers on:

- `compile-nl`
- `compile-dsl`
- `search`
- `plan`
- `retrieve`
- `index`
- `context`
- `compare`
- `export-symbols`

Compatibility aliases still exist for older stage-language commands such as:

- `hybrid-plan`
- `hybrid-search`
- `hybrid-compare`
- `rag-sync`
- `rag-search`

### Retrieval package rename

The canonical experimental package is now:

- `experimental.retrieval_orchestrator`

Compatibility remains in place for:

- `experimental.hybrid_orchestrator`

This means new code should use the retrieval-oriented package name, while older imports still keep working.

### Environment and dependencies

- local virtual environment support is documented
- `chromadb` is installed and verified
- `rich` was added for the terminal preview prototype

### Terminal dashboard and prototype work

- `seam.py --db seam.db dashboard` now launches a real runtime-connected terminal dashboard
- the dashboard supports live interactive use plus scripted `--run` commands for smoke testing
- the older `branding/` work still exists as design/prototype material

## What Was Cleaned Up

- transient handoff docs were removed
- generated NotebookLM export artifacts were removed from the repo
- `.gitignore` now ignores `exports/`
- conversation/share links were checked for and none were found

## What Still Needs Work

### 1. Decide where retrieval lives long-term

We still need to decide whether the retrieval orchestrator should:

- stay under `experimental/`
- move into `seam_runtime`

If promoted, `index` and `context` should become clearly first-class runtime features.

### 2. Richer context output

`context` currently returns a pack-oriented result.
We likely want additional output modes such as:

- plain prompt text
- citation/evidence mode
- summarized record mode
- exact record mode

### 3. Documentation alignment

Some documentation still uses older wording.
The repo should consistently describe the system using:

- compile
- search
- retrieval
- index
- context
- export

### 4. Productization of the terminal surface

The runtime-connected terminal dashboard now exists, but it is still an early operator surface rather than a fully polished product UI.
If we want it to become real product surface area, we need to decide whether to build:

- a true TUI
- a browser shell
- a startup/dashboard mode for the CLI

## Immediate Next Step

Best next implementation task:

Add richer `context` output modes so SEAM can emit prompt-ready text, evidence/citation views, summaries, and exact-record payloads depending on the operator need.

## Working Rule

When resuming work in a new conversation:

1. Read this file first.
2. Then read `REPO_LEDGER.md` for deeper project history and maintenance context.
3. Confirm the current task against both files.
4. Update this file whenever a major milestone or direction changes.

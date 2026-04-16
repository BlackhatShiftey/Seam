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

The CLI is usable now, but not "finished" in the sense of product polish. Core flows work. The biggest remaining runtime gap is stronger structured retrieval in the SQL leg.

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

### Branding/prototype work

There is a terminal-style branding prototype in `branding/`.
It is a design prototype, not yet a shipped runtime surface.

## What Was Cleaned Up

- transient handoff docs were removed
- generated NotebookLM export artifacts were removed from the repo
- `.gitignore` now ignores `exports/`
- conversation/share links were checked for and none were found

## What Still Needs Work

### 1. Stronger structured retrieval

The current SQL leg is still too lightweight.
We should push more filtering and ranking into SQLite for:

- `kind`
- `scope`
- `namespace`
- `predicate`
- `subject`
- `object`
- lexical relevance

Goal:
- make structured queries do more useful work before vector fallback

### 2. Decide where retrieval lives long-term

We still need to decide whether the retrieval orchestrator should:

- stay under `experimental/`
- move into `seam_runtime`

If promoted, `index` and `context` should become clearly first-class runtime features.

### 3. Richer context output

`context` currently returns a pack-oriented result.
We likely want additional output modes such as:

- plain prompt text
- citation/evidence mode
- summarized record mode
- exact record mode

### 4. Documentation alignment

Some documentation still uses older wording.
The repo should consistently describe the system using:

- compile
- search
- retrieval
- index
- context
- export

### 5. Productization of the terminal surface

The terminal branding/prototype work is visually useful, but it is still separate from the actual CLI/runtime.
If we want it to become real product surface area, we need to decide whether to build:

- a true TUI
- a browser shell
- a startup/dashboard mode for the CLI

## Immediate Next Step

Best next implementation task:

Strengthen the SQLite retrieval leg so filtered retrieval is meaningfully better and more explainable before semantic/vector fallback.

## Working Rule

When resuming work in a new conversation:

1. Read this file first.
2. Then read `REPO_LEDGER.md` for deeper project history and maintenance context.
3. Confirm the current task against both files.
4. Update this file whenever a major milestone or direction changes.

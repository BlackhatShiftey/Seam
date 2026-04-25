# AGENTS.md

Canonical multi-agent protocol for this repo. All models use the same rules.

## Session Start

Read in order:
1. `PROJECT_STATUS.md`
2. `REPO_LEDGER.md`
3. `HISTORY_INDEX.md`
4. `docs/CODE_LAYOUT.md`

Then:
- Prefer latest valid snapshot in `.seam/snapshots/`.
- If snapshot verification fails, fall back to index-first reads.
- Never read all of `HISTORY.md`; pull only needed entries by indexed line/byte ranges.
- Treat `archive/code/`, `docs/archive/`, `build/`, `.venv/`, and generated/cache paths as inactive unless the user explicitly asks for historical or retired material.
- For normal code search, stay in active paths: `seam_runtime/`, `seam.py`, `experimental/`, `tools/`, `scripts/`, `installers/`, `docs/`, tests, and root status files.

## Session End

If state changed:
1. Append one entry to `HISTORY.md`.
2. Rebuild `HISTORY_INDEX.md`.
3. Write one snapshot JSON.

Use `tools/history/*` scripts for entry writes, index rebuild, integrity verification, and snapshot creation.

## Invariants

- `HISTORY.md` is append-only.
- `HISTORY_INDEX.md` is derived state.
- Snapshot integrity must be verified before use.
- Status updates never edit old entries; use `supersedes`.
- Use pointer cards across docs (`see HISTORY#NNN`), not duplicated prose.
- Active docs/code and archived docs/code must stay separated; do not copy stale archive prose or code back into active paths without rewriting and verifying it.

## Entry Schema

Required fields per entry:
`id`, `date`, `agent`, `status`, `topics`, `commits`, `refs`, `supersedes`, `tokens`, and body.

Valid status values:
`planned`, `in-progress`, `done`, `changed`, `deferred`, `abandoned`.

## Topic Vocabulary

Only use tags from this controlled set:

`compile, mirl, persist, verify, retrieval, search, rank, vector, sbert, chroma, pgvector, lexical, compress, lx1, roundtrip, codec, benchmark, holdout, bundle, fixture, diff, gold-standard, dashboard, tui, textual, animation, graph, chat, installer, windows, linux, wsl2, pyproject, extras, command, doctor, demo, naming, alias, readme, ledger, roadmap, plan, status, history, session, handoff, snapshot, mcp, multi-agent, protocol, integrity`

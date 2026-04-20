# SEAM Repo Ledger

Last updated: 2026-04-20

This ledger is the stable engineering memory for repo-level decisions only.
Detailed session history, milestones, and plan transitions now live in `HISTORY.md`
and `HISTORY_INDEX.md`.

## Startup Read Order

1. `PROJECT_STATUS.md` (current state)
2. `AGENTS.md` (cross-agent protocol)
3. `HISTORY_INDEX.md` (history map)
4. `HISTORY.md` only by surgical read using indexed line/byte ranges

## Project Identity

- `SEAM`: runtime/tool identity
- `MIRL`: canonical memory IR
- `PACK`: derived prompt-time context representation
- `SEAM-LX/1`: exact machine-text envelope for lossless workflows

## Stable Decisions

- SQLite is canonical source of truth.
- Vector stores (SQLite vector index, Chroma, PgVector) are derived retrieval layers.
- Lossless claims require exact reconstruction and integrity checks.
- Benchmark claims must be auditable (bundle hash, case hashes, fixture hashes, git SHA).
- Compatibility CLI aliases are acceptable during naming transitions.
- Agent continuity is protocol-driven (`AGENTS.md`), not model-specific duplicate docs.
- Cross-file duplication is disallowed; use pointer cards (`see HISTORY#NNN`).

## Handoff Policy

- Default: record state via `HISTORY.md` entries + `HISTORY_INDEX.md`.
- Session close writes one validated snapshot in `.seam/snapshots/`.
- `HISTORY_INDEX.md` and snapshots are derived artifacts; `HISTORY.md` is authoritative.
- The `handoff/archive` branch is reserved for PDF and handoff artifact publication, not primary runtime/source work.

## Benchmark Publication Policy

Published benchmark statements must include:

- command used
- bundle hash
- per-case hashes
- fixture hashes
- tokenizer/dependency state
- git SHA

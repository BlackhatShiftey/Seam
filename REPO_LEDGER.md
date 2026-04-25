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

## Documentation Separation Policy

- Active operator and engineering docs live in `docs/` and are indexed by `docs/README.md`.
- Inactive docs, old handoffs, superseded setup notes, and historical coding artifacts live under `docs/archive/`.
- Archived docs are traceability records, not current instructions.
- When old prose is useful, rewrite the current part into an active doc and point to `HISTORY#NNN`; do not duplicate stale context across active docs.

## Code Separation Policy

- Active runtime code lives in `seam_runtime/` and `seam.py`.
- Active operator/dev tooling lives in `tools/`, `scripts/`, and `installers/`.
- `experimental/` is active prototype code: less stable than runtime code, but still importable and testable.
- Inactive or retired code lives under `archive/code/` and must not be imported, packaged, or used as current behavior.
- Generated build copies live in ignored paths (`build/` or `archive/code/generated-build*/`) and should not guide implementation decisions.
- The current code map is `docs/CODE_LAYOUT.md`.

## Runtime Service Safety Policy

- External services for real-adapter tests (for example Docker pgvector) must be started only for the active test window.
- Every service started for a test run must be explicitly stopped and removed at the end of that run.
- Prefer non-conflicting ports for temporary services and verify they are released after cleanup.
- Keep resource monitoring lightweight during runs (snapshot checks or low-frequency polling) to avoid adding load.
- If a run fails or exits early, perform the same shutdown/cleanup sequence before continuing.
- Default guardrail for local runs: warn around `82%` RAM usage and treat `90%` RAM as hard limit unless explicitly overridden for a task.
- Use `C:\Users\iwana\OneDrive\Documents\Codex\scripts\run_guarded.ps1` for heavy commands so CPU/RAM/disk are watched during execution.
- Use `C:\Users\iwana\OneDrive\Documents\Codex\scripts\run_real_adapters_guarded.ps1` for end-to-end real-adapter validation; it starts pgvector, runs guarded checks, and cleans up containers/artifacts on exit.
- Archive benchmarks with `C:\Users\iwana\OneDrive\Documents\Codex\scripts\store_benchmark.ps1` to keep publication-required hashes and reproducibility metadata in Documents; outputs are sequence+time indexed and blocked from writing inside the git repo by default.

## Benchmark Publication Policy

Published benchmark statements must include:

- command used
- bundle hash
- per-case hashes
- fixture hashes
- tokenizer/dependency state
- git SHA

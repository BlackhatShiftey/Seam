# SEAM Project Status

Last updated: 2026-04-20

## Current State

SEAM is operating as a local machine-first memory runtime with:

- MIRL compile/verify/persist/search/context flows in production use
- structured + vector retrieval and runtime dashboard surface
- lossless SEAM-LX/1 compression with integrity verification
- PgVector support and installer coverage across Windows/Linux paths

## What Is Stable

- Core runtime paths (compile, verify, persist, search, context, benchmark)
- Dashboard snapshot/smoke-test behavior
- Benchmark bundle verification workflow
- Durable history protocol (`AGENTS.md`, `HISTORY.md`, `HISTORY_INDEX.md`)

## Active Focus

- Reduce startup context overhead by relying on compact index + surgical history reads
- Keep roadmap execution tied to history entries and supersedes chains
- Continue feature delivery without reintroducing duplicated continuity text
- Run real-adapter validation through guarded scripts to enforce resource ceilings and automatic service cleanup

## Operational Baseline

- Use `scripts/run_real_adapters_guarded.ps1` for end-to-end real adapter checks.
- Use `scripts/run_guarded.ps1` for heavy local commands where CPU/RAM/disk guardrails are needed.
- Use `scripts/store_benchmark.ps1` to archive benchmark runs under Documents with sequence+time folders, run index, and publication metadata/hashes.
- Default memory guardrails are `82%` warning and `90%` hard limit.

## Working Rule

When resuming:

1. Read `PROJECT_STATUS.md`.
2. Read `AGENTS.md`.
3. Read `HISTORY_INDEX.md`.
4. Pull only required `HISTORY.md` entries by index offsets.

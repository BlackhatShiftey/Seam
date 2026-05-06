# SEAM Repo Ledger

Last updated: 2026-05-06

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
- `SEAM-HS/1`: lossless PNG-backed Holographic Surface for visual memory snapshots

## Stable Decisions

- This GitHub repo is the private source-of-truth home for SEAM runtime,
  tooling, docs, tests, and repo-owned fixtures. A separate repo will hold
  user-file surfaces or user-facing file sets when that workflow is created.
- SEAM is proprietary source-available software if any repo or artifact is
  later made public. Public repository visibility does not grant open-source
  rights; commercial, hosted, embedded, derivative, redistribution, or
  closed-source use is available only with separate written permission through
  a commercial license.
  The controlling files are `LICENSE` and `NOTICE`; `COMMERCIAL_LICENSE.md`
  is the plain-language commercial-use boundary.
- SEAM accepts contributions only under a contributor grant that lets the
  project owner keep developing, sublicensing, relicensing, and commercially
  licensing SEAM without later contributor permission. The contributor-facing
  summary lives in `CONTRIBUTING.md`.
- Security-sensitive reports should be handled privately through `SECURITY.md`;
  do not disclose private data, credential material, customer data, or exploit
  details in public issues.
- `docs/PROTECTION_MODEL.md` documents the public/private repo split and must
  not be added to the mandatory startup read list unless the task touches
  licensing, contribution policy, repo protection, or public/private separation.
- Protection-only changes must not silently alter runtime behavior, package
  metadata, CLI commands, installer behavior, dashboard behavior, API behavior,
  benchmark behavior, or history tooling behavior.
- SQLite is canonical source of truth.
- Vector stores (SQLite vector index, Chroma, PgVector) are derived retrieval layers.
- Document ingest status is canonical SQLite metadata. Source refs, source hashes, extraction status, index status, and deletion state belong in `document_status`, not only in derived vector stores.
- Agent-facing retrieval should use progressive disclosure where possible: compact search/index results first, then full MIRL records by selected IDs.
- Default agent RAG should prefer `mix` retrieval only after benchmark validation; the supported retrieval modes are `vector`, `graph`, `hybrid`, and `mix`.
- Agent ecosystem integrations should be thin wrappers over SEAM CLI/REST/stdio bridge surfaces. Do not rewrite the Python runtime into Node just to fit Claude Code-style plugin ecosystems.
- Lossless claims require exact reconstruction and integrity checks.
- SEAM compression must produce directly readable AI-native machine language as the primary artifact; opaque byte compression is only an optional reconstruction/integrity backing layer.
- A compressed SEAM artifact is not complete unless SEAM can answer detail questions from the compressed language without restoring the original source.
- Holographic surfaces are queryable visual containers for embedded MIRL or `SEAM-RC/1`; they are not a replacement for SQLite canonical truth and are not a claim of free compression.
- `seam surface compile` is the default source-to-surface operator flow: compile source text into MIRL, then encode MIRL into `SEAM-HS/1` with `rgb24` unless a denser mode is explicitly requested.
- Benchmark claims must be auditable (bundle hash, case hashes, fixture hashes, git SHA), diffed against a prior run, pass the benchmark gate, and stay separated from publish-only holdout runs.
- Benchmark evidence proves SEAM value but never expands license rights; hosted,
  SaaS, commercial, embedded, redistribution, customer-deployment, or
  closed-source use still requires a separate written commercial license.
- Compatibility CLI aliases are acceptable during naming transitions.
- Agent continuity is protocol-driven (`AGENTS.md`), not model-specific duplicate docs.
- Cross-file duplication is disallowed; use pointer cards (`see HISTORY#NNN`).

## AI-Native Compression Policy

- The compressed language is the working document for AI question answering.
- Direct readability is mandatory for documents, text, images, audio, and video: quotes, table cells, OCR spans, image regions, timestamps, transcript spans, and provenance must be represented in machine-readable records.
- Opaque payload formats such as SEAM-LX/1 may be retained for exact rebuilds and hash checks, but they must not be the only artifact used for semantic read/query workflows.
- Future compression interpreters and codecs must optimize intelligence per token while preserving exact detail access through MIRL or a successor SEAM machine language.
- SEAM-HS/1 may carry MIRL, RC/1, LX/1, or raw bytes in lossless PNG pixels. MIRL and RC/1 payloads are directly queryable from the surface; LX/1 payloads are verify/decode only until converted into a readable payload.
- The planned surface library stores `.seam.png` artifacts as addressable visual memory surfaces with SQLite metadata, hashes, verification state, and lookup fields. Queries should read embedded MIRL/RC payloads directly from the lossless image bytes in memory; PACK remains derived prompt-time context and must not become the raw image store.
- The private runtime repo stores source and metadata code for surface-library
  adapters, not generated operator/user `.seam.png` artifacts by default.
  Generated surface files stay operator-controlled unless explicitly promoted
  as repo-owned fixtures or documentation assets.

## Handoff Policy

- Default: record state via `HISTORY.md` entries + `HISTORY_INDEX.md`.
- Session close writes one validated snapshot in `.seam/snapshots/`.
- `HISTORY_INDEX.md` and snapshots are derived artifacts; `HISTORY.md` is authoritative.
- The `handoff/archive` branch is reserved for PDF and handoff artifact publication, not primary runtime/source work.

## Temporal Continuity Policy

- Every material repo change must produce an append-only `HISTORY.md` entry, rebuilt `HISTORY_INDEX.md`, verified integrity, and one validated snapshot.
- History entries must preserve the temporal chain: previous state, new state, `supersedes` link when applicable, successes, failures, skipped verification, changed files, and unresolved next steps.
- Stable repo facts live here in `REPO_LEDGER.md`; detailed session chronology lives in `HISTORY.md`. Do not duplicate long prose across both files.
- Agents must update this ledger when changing stable repo policy, architecture, active/archive routing, runtime safety rules, durable operator workflows, benchmark publication rules, or cross-agent protocol.
- Agents must update `PROJECT_STATUS.md` when the current operating state or active focus changes.
- Model-specific guides such as `CLAUDE.md`, `GEMINI.md`, and `ANTIGRAVITY.md` must route back to `AGENTS.md` and must not create a competing protocol.

## Context Budget Policy

- Full continuity is preserved in append-only history, but normal startup must not load full history.
- `HISTORY_INDEX.md` is the compact route map; `.seam/snapshots/` are bounded handoff packs; `tools.history.build_context_pack` builds topic/latest/supersedes packs under an explicit token budget.
- `tools.history.verify_continuity` is the quality gate for history/index/snapshot freshness, supersedes validity, and session-link/secret hygiene.
- Prefer task-specific context packs over broad scans. If a pack is insufficient, add targeted topics, explicit entries, or refs instead of reading all of `HISTORY.md`.

## Data Routing Policy

- `tools/history/routing_manifest.json` defines logical branches for AI-searchable history such as `maintenance/docker`, `maintenance/pgvector`, `protocol/context`, and `protocol/security`.
- Route classifications are mutable, but route mutations must remain reconstructable through `HISTORY.md`, manifest lifecycle fields, and stable topic ledgers under `docs/ledgers/`.
- `tools.history.verify_routing` checks route tree integrity, parent links, route lifecycle fields, ledger paths, and referenced history entries.
- Deleting a classification means removing it from active use through `status=retired` or `status=moved`; the audit trail must remain.

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

## REST API Policy

- The REST API is optional and installed with the `server` extra.
- `seam serve` and `seam-server` run the FastAPI/Uvicorn surface against the configured SQLite database.
- Protected endpoints require `Authorization: Bearer <token>` when `SEAM_API_TOKEN` is set; leave that variable unset only for trusted local development.
- `/health` is unauthenticated for local service checks but still participates in the same rate limiter.
- Rate limiting is configured by `SEAM_API_RATE_LIMIT_PER_MINUTE` or `SEAM_API_RATE_LIMIT`; `0` or unset disables the limiter.
- API handlers must use existing `SeamRuntime` behavior and public report `to_dict()` methods rather than inventing parallel response fields.

## Benchmark Publication Policy

Holographic Surface claims must report `surface_exact_rate`, payload hash match
rate, direct query exactness, and the PNG mode (`bw1`, `rgb`/`rgb24`,
explicit `rgba32`, or explicit `rgba64`).

Published benchmark statements must include:

- command used
- bundle hash
- per-case hashes
- fixture hashes
- tokenizer/dependency state
- git SHA
- benchmark diff output comparing the claim run against its baseline
- benchmark gate output from `seam benchmark gate <bundle> [--baseline <run-a>]`
- holdout result bundle when the statement is an external or publication claim

Holdout benchmark fixtures live under `benchmarks/fixtures/holdout/` and are ignored by git by default. They must be run only with `seam benchmark run --holdout --confirm-holdout`, and default holdout result bundles are written separately under `benchmarks/runs/holdout/`.

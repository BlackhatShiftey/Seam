# SEAM Project Status

Last updated: 2026-05-01

## Current State

SEAM is operating as a local machine-first memory runtime with:

- MIRL compile/verify/persist/search/context flows in production use
- Full Textual interactive TUI dashboard with chat panel, command palette (/, !, ?), MIRL animation, independently scrollable panes, IDE-style explorer tree, status bar, colored RichLog panels, focus zoom toggle, runtime-smoked Settings tab, and live Overview health bars for database, pgvector, API/config, and settings paths
- Dashboard chat with expanded OpenRouter model defaults (Qwen, DeepSeek, MiMo, Kimi, GLM, Claude, Gemini, Grok, Gemma, Pareto Code Router)
- lossless SEAM-LX/1 compression with integrity verification
- SEAM-HS/1 Holographic Surface PNG snapshots with automatic source-to-MIRL surface compile, direct MIRL/RC query, verify, decode, context, and import commands
- benchmark diff tooling, pass/fail gate tooling, publish-only holdout fixture routing, and tracked CI coverage
- optional FastAPI/Uvicorn REST API surface for local compile, search, context, stats, health, persist, and lossless-compression workflows
- PgVector support running locally via Docker Compose on port 55432; installer coverage across Windows/Linux paths
- Competitive RAG/install polish in progress on `codex/competitive-rag-install-polish`: one-line private install docs, product-first README, document status tracking, progressive memory search/get, `retrieve --mode vector|graph|hybrid|mix`, stdio agent bridge, and vector stale-index reporting
- Active/inactive code and docs separation enforced via `docs/CODE_LAYOUT.md`, `.rgignore`, and archive paths

## What Is Stable

- Core runtime paths (compile, verify, persist, search, context, benchmark)
- Textual dashboard (interactive TUI, chat, slash palette, reload command, MIRL animation, independent pane scrolling including Settings and Overview, ExplorerTree navigation, status bar, colored Rich markup panels, focus zoom toggle, Settings tab, and live Overview health bars)
- Dashboard installers: `seam-dash` shim on Windows (`.cmd`) and POSIX; `seam-dash` entrypoint in `pyproject.toml`
- Dashboard launcher: `scripts/windows/launch_dashboard.bat` + `launch_dashboard.ps1`; propagates pgvector config from `SEAM_LOCAL_ENV` or a private Documents `SEAM\local\.env`
- pgvector real adapter: Docker Compose service `seam-pgvector` (image `pgvector/pgvector:0.8.2-pg18-trixie`, port 55432)
- Dashboard snapshot/smoke-test behavior
- Benchmark bundle verification, diff, gate, holdout workflow, and Windows GitHub Actions workflow (see HISTORY#095)
- REST API skeleton: `seam serve`, `seam-server`, optional `server` extra, bearer-token protected endpoints, and env-configurable rate limiting
- RAG efficiency surface: `seam ingest <path> --persist`, `seam memory search`, `seam memory get`, `seam retrieve --mode mix`, document status rows, vector source-hash cache/stale checks, and `seam mcp serve` stdio bridge
- Holographic Surface surface commands: `seam surface compile|encode|decode|verify|query|search|context|import`; `bw1`, `rgb24`, and explicit `rgba32`; `surface` benchmark exactness gate
- Durable history protocol (`AGENTS.md`, `HISTORY.md`, `HISTORY_INDEX.md`)
- Active/inactive separation: `docs/CODE_LAYOUT.md` maps live vs archived paths; `.rgignore` gates code search
- Token-bounded context loading via history snapshots and `tools.history.build_context_pack`
- Route-aware data classification through `tools/history/routing_manifest.json` and `docs/ledgers/`

## Active Focus

- Reduce startup context overhead by relying on compact index + surgical history reads
- Preserve near-complete temporal history without loading all history into model context
- Keep maintenance, security, context, and runtime facts logically routed for AI search without duplicating chronology
- Make compression produce directly readable AI-native machine language, with opaque byte payloads used only as optional reconstruction/integrity backing layers
- Treat SEAM-HS/1 Holographic Surface as a queryable visual snapshot layer for MIRL/RC payloads, not as free compression or a replacement for SQLite truth
- Make the full functional visual-memory loop shippable: documents compile into directly readable MIRL/RC, MIRL/RC packs into SEAM-HS/1 PNG surfaces, stored surfaces remain addressable by metadata/hash, and query/context can read the embedded payload directly from the image surface without restoring the original document
- Keep roadmap execution tied to history entries and supersedes chains
- Turn the competitive plan into shippable surfaces: finish README/install polish, graph/vector/mix retrieval hardening, agent bridge docs, and benchmark coverage without breaking existing CLI aliases
- Continue feature delivery without reintroducing duplicated continuity text
- Run real-adapter validation through guarded scripts to enforce resource ceilings and automatic service cleanup
- Roadmap planned items (#028–#047) are open except benchmark holdout suites (#036/C1), benchmark diff tooling (#037/C2), and REST API surface (#046/E3), which are implemented: dashboard animations, benchmark progress bars, sparkline graphs, command terminology audit, BEIR/MTEB benchmarks, Claude tool set, auto-compression pipeline, batch compile, PgVector migration helper, multi-tenant namespacing

## Operational Baseline

- Use `scripts/windows/launch_dashboard.bat` (wraps `launch_dashboard.ps1`) to start the dashboard on Windows with pgvector configured. Use `/reload` or `reload` inside the dashboard to rebuild dashboard panels, metrics, and chart state without restarting.
- Use `scripts/run_real_adapters_guarded.ps1` for end-to-end real adapter checks.
- Use `scripts/run_guarded.ps1` for heavy local commands where CPU/RAM/disk guardrails are needed.
- Use `scripts/store_benchmark.ps1` to archive benchmark runs under Documents with sequence+time folders, run index, and publication metadata/hashes.
- Use `seam benchmark diff <run-a> <run-b>` before claiming a benchmark improvement, `seam benchmark gate <bundle> [--baseline <run-a>]` before merge/release, and `seam benchmark run --holdout --confirm-holdout` only for publish-time audits.
- Use `python -m tools.history.build_context_pack --topics <tags> --latest <n> --token-budget <budget>` for bounded task context.
- Use `python -m tools.history.verify_continuity` before ending a changed session.
- Use `python -m tools.history.verify_routing` after changing data classifications or ledgers.
- Default memory guardrails are `82%` warning and `90%` hard limit.
- pgvector Docker Compose: `docker compose --env-file <private-env> up -d seam-pgvector`; port 55432; credentials stay outside the repo.

## Working Rule

When resuming:

1. Read `PROJECT_STATUS.md`.
2. Read `AGENTS.md`.
3. Read `HISTORY_INDEX.md`.
4. Pull only required `HISTORY.md` entries by index offsets.

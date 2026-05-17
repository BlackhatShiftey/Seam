# SEAM Project Status

Last updated: 2026-05-17

## Current State

SEAM is operating as a local machine-first memory runtime with:

- MIRL compile/verify/persist/search/context flows in production use
- Full Textual interactive TUI dashboard with chat panel, command palette (/, !, ?), MIRL animation, independently scrollable panes, IDE-style explorer tree, status bar, colored RichLog panels, focus zoom toggle, runtime-smoked Settings tab, and live Overview health bars for database, pgvector, API/config, and settings paths
- Dashboard chat with expanded OpenRouter model defaults (Qwen, DeepSeek, MiMo, Kimi, GLM, Claude, Gemini, Grok, Gemma, Pareto Code Router)
- First interactive agent-style CLI shell: `seam shell` / `seam chat` for persistent memory remember/search/context/stats/doctor workflows
- lossless SEAM-LX/1 compression with integrity verification
- SEAM-HS/1 Holographic Surface PNG snapshots with automatic source-to-MIRL surface compile, direct MIRL/RC query, verify, decode, context, and import commands
- HS/1 surface library adapters landed on `main`: stored surface metadata, stable `hs:<hash>` IDs, list/show/repair, redundant file-backed copies, and direct query/verify/decode/context/import by stored ID
- benchmark diff tooling, pass/fail gate tooling, publish-only holdout fixture routing, and tracked CI coverage
- optional FastAPI/Uvicorn REST API surface for local compile, search, context, stats, health, persist, and lossless-compression workflows
- agent-safe MCP stdio server for Gemini/Claude/Cursor-style MCP clients, plus legacy JSON-lines bridge, with compact memory search/get, ingest, stats, document status, context packing, doctor, stored HS/1 surface operations, and benchmark run summaries
- PgVector support running locally via Docker Compose on port 55432; installer coverage across Windows/Linux paths
- Competitive RAG/install polish in progress on `codex/competitive-rag-install-polish`: one-line private install docs, product-first README, document status tracking, progressive memory search/get, `retrieve --mode vector|graph|hybrid|mix`, stdio agent bridge, and vector stale-index reporting
- Active/inactive code and docs separation enforced via `docs/CODE_LAYOUT.md`, `.rgignore`, and archive paths
- IDE-like browser dashboard under `experimental/webui/` currently launches the preserved original prototype from `prototype-backup/` at the Vite root so the IDE shell, graphs, settings, terminal, and chat remain visible while the REST-wired TypeScript panes are reworked.

## Current Resume Point

- `main` is the source-of-truth branch. After pulling, verify local `HEAD` equals `origin/main` before starting new work.
- Latest continuity handoff is `HISTORY#163`. Snapshot JSON files are local derived artifacts, so a fresh Linux clone should regenerate the resume snapshot with the command in `docs/setup.md` before running continuity verification.
- A fresh Linux clone should run the repo-local setup in `docs/setup.md`, then verify `python -m tools.history.verify_integrity`, `python -m tools.history.verify_routing`, and `python -m tools.history.verify_continuity` before starting new work.
- Next work should continue from the IDE-like web dashboard / REST API GUI, Agent Compiler roadmap, and first-class agent CLI direction, not from the already-merged HS/1 adapter/repair/benchmark branches.

## What Is Stable

- Core runtime paths (compile, verify, persist, search, context, benchmark)
- Textual dashboard (interactive TUI, chat, slash palette, reload command, MIRL animation, independent pane scrolling including Settings and Overview, ExplorerTree navigation, status bar, colored Rich markup panels, focus zoom toggle, Settings tab, and live Overview health bars)
- Dashboard installers: `seam-dash` shim on Windows (`.cmd`) and POSIX; `seam-dash` entrypoint in `pyproject.toml`
- Dashboard launcher: `scripts/windows/launch_dashboard.bat` + `launch_dashboard.ps1`; propagates pgvector config from `SEAM_LOCAL_ENV` or a private Documents `SEAM\local\.env`
- pgvector real adapter: Docker Compose service `seam-pgvector` (image `pgvector/pgvector:0.8.2-pg18-trixie`, port 55432)
- Dashboard snapshot/smoke-test behavior
- Benchmark bundle verification, diff, gate, holdout workflow, and Windows GitHub Actions workflow (see HISTORY#095)
- REST API skeleton: `seam serve`, `seam-server`, optional `server` extra, bearer-token protected endpoints, and env-configurable rate limiting
- RAG efficiency surface: `seam ingest <path> --persist`, `seam memory search`, `seam memory get`, `seam retrieve --mode mix`, document status rows, vector source-hash cache/stale checks, and `seam mcp stdio` MCP server
- MCP agent bridge: `seam mcp stdio` and `seam-mcp` expose 16 bounded, documented tools over standard MCP JSON-RPC for Gemini/Claude/Cursor-style clients; Gemini's project config starts it with `--ensure-pgvector` so Docker Compose pgvector is healthy before MCP tool discovery; `seam mcp serve` remains as the legacy JSON-lines bridge. Tools cover memory retrieval, controlled ingest, context, install diagnostics, stored HS/1 surfaces, index status, retrieval modes, and benchmark summaries; canonical `hs:<hex>` surface refs are required for surface tools.
- Interactive CLI shell: `seam shell` and `seam chat` provide the first REPL-style memory interface, with slash commands and prompt-ready context output
- Holographic Surface surface commands: `seam surface compile|encode|decode|verify|query|search|context|import`; `bw1`, `rgb`/`rgb24`, explicit `rgba32`, and explicit `rgba64`; `surface` benchmark exactness gate, stored lookup gate, stored query gate, repair gate, and repair-query gate
- Holographic Surface library commands: `seam surface store|list|show|repair`, plus `compile --store` and `encode --store` for SQLite metadata registration, redundant file-backed copies, and repair of missing/corrupt stored copies without committing generated user artifacts
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
- Make the full functional visual-memory loop shippable: documents compile into directly readable MIRL/RC, MIRL/RC packs into SEAM-HS/1 PNG surfaces, stored surfaces remain addressable by metadata/hash, query/context can read the embedded payload directly from the image surface without restoring the original document, and the surface benchmark gates stored lookup plus repair at 100%
- Keep this private GitHub repo as the source-of-truth home for runtime files while leaving generated/operator user surfaces out of git unless deliberately promoted as fixtures or docs assets; future user-file sets belong in a separate repo
- Keep roadmap execution tied to history entries and supersedes chains
- Turn the competitive plan into shippable surfaces: finish README/install polish, graph/vector/mix retrieval hardening, agent bridge docs, and benchmark coverage without breaking existing CLI aliases
- Build the Agent Compiler workstream from `docs/roadmap/AGENT_COMPILER.md`: compile canonical SEAM protocol into model-specific adapters, benchmark those adapters, and audit installed local skills before applying changes.
- Continue hardening `experimental/webui/` as the SEAM browser dashboard/REST API GUI: preserve the original IDE-like shell first, then port real endpoint coverage into that shell without regressing graphs, settings, terminal, or chat.
- Turn the SEAM CLI into a first-class agent CLI like Gemini/Claude/Codex CLI: keep `seam shell` as the entrypoint, then add model routing, tool execution, repo/context awareness, command history, and guardrails on top of SEAM memory.
- Continue feature delivery without reintroducing duplicated continuity text
- Run real-adapter validation through guarded scripts to enforce resource ceilings and automatic service cleanup
- Track I (external memory benchmarks) handoff series is fully specified across five SOPs in `docs/SOP_EXTERNAL_BENCH_*.md` (Phase 1+2 registry/runner/CLI, SEAM LoCoMo adapter, LLM-judge scoring, Mem0 comparator, Zep comparator). Each SOP has a DeepSeek implementation checklist and a reviewer verification checklist; pick them up sequentially. See `HISTORY#165`.
- Legacy roadmap entries `HISTORY#028`-`HISTORY#047` remain append-only planning cards. `HISTORY#036` (holdout suites), `HISTORY#037` (benchmark diff tooling), and `HISTORY#046` (REST API surface) are implemented and superseded by `HISTORY#152`, `HISTORY#153`, and `HISTORY#154`; use `ROADMAP.md` Recommended Course for current priority.

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
- pgvector Docker Compose: `docker compose --env-file <private-env> up -d pgvector`; container `seam-pgvector`; port 55432; credentials stay outside the repo. Agent MCP startup can automate this with `seam-mcp --ensure-pgvector`.

## Working Rule

When resuming:

1. Read `PROJECT_STATUS.md`.
2. Read `REPO_LEDGER.md`.
3. Read `HISTORY_INDEX.md`.
4. Read `docs/CODE_LAYOUT.md`.
5. Read `docs/DATA_ROUTING.md` when the task touches history, ledgers, maintenance records, routing, context budget, or auditability.
6. Pull only required `HISTORY.md` entries by index offsets or with `python -m tools.history.build_context_pack`.

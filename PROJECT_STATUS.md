# SEAM Project Status

Last updated: 2026-05-17

## Current State

SEAM is operating as a local machine-first memory runtime with:

- MIRL compile/verify/persist/search/context flows in production use
- External memory benchmark registry + `seam bench external` CLI alias (Track I SOP 0 landed)
- SEAM LoCoMo adapter with string-match scoring + 60s quickstart fixture (Track I SOP 1 landed; `seam bench external --quickstart locomo`)
- Full Textual interactive TUI dashboard with chat panel, command palette (/, !, ?), MIRL animation, independently scrollable panes, IDE-style explorer tree, status bar, colored RichLog panels, focus zoom toggle, runtime-smoked Settings tab, and live Overview health bars for database, pgvector, API/config, and settings paths
- Dashboard chat with expanded OpenRouter model defaults (Qwen, DeepSeek, MiMo, Kimi, GLM, Claude, Gemini, Grok, Gemma, Pareto Code Router)
- First interactive agent-style CLI shell: `seam shell` / `seam chat` for persistent memory remember/search/context/stats/doctor workflows
- lossless SEAM-LX/1 compression with integrity verification
- SEAM-HS/1 Holographic Surface PNG snapshots with automatic source-to-MIRL surface compile, direct MIRL/RC query, verify, decode, context, and import commands
- HS/1 surface library adapters landed on `main`: stored surface metadata, stable `hs:<hash>` IDs, list/show/repair, redundant file-backed copies, and direct query/verify/decode/context/import by stored ID
- benchmark diff tooling, pass/fail gate tooling, publish-only holdout fixture routing, and tracked CI coverage
- optional FastAPI/Uvicorn REST API surface for local compile, search, context, stats, health, persist, and lossless-compression workflows, with bounded request bodies and authenticated remote-bind guardrails
- agent-safe MCP stdio server for Gemini/Claude/Cursor-style MCP clients, plus legacy JSON-lines bridge, with compact memory search/get, ingest, stats, document status, context packing, doctor, stored HS/1 surface operations, and benchmark run summaries
- PgVector support running locally via Docker Compose on port 55432; installer coverage across Windows/Linux paths
- Linux installer supports two explicit modes: default global command install under `~/.local/share/seam`, and `--dev` repo-local Python bootstrap with the external-drive `.venv/lib64` fallback plus SEAM protocol verification; WebUI setup remains separate.
- Competitive RAG/install polish in progress on `codex/competitive-rag-install-polish`: one-line private install docs, product-first README, document status tracking, progressive memory search/get, `retrieve --mode vector|graph|hybrid|mix`, stdio agent bridge, and vector stale-index reporting
- Active/inactive code and docs separation enforced via `docs/CODE_LAYOUT.md`, `.rgignore`, and archive paths
- IDE-like browser dashboard under `experimental/webui/` currently launches the preserved original prototype from `prototype-backup/` at the Vite root so the IDE shell, graphs, settings, terminal, and chat remain visible while the REST-wired TypeScript panes are reworked.
- Adaptive SEAM Skill Factory foundation is merged on `main` through PR #21; current tracked code includes Skill Factory primitives and roadmap docs under `seam_runtime/skills/` and `docs/roadmap/SKILL_FACTORY.md`.

## Current Resume Point

- `main` is the source-of-truth branch. After pulling, verify local `HEAD` equals `origin/main` before starting new work.
- Latest continuity handoff is `HISTORY#188` — SOP 2 LLM-judge landed with string-match scoring, per-scope SQLite isolation, and 60s quickstart fixture; all tests pass (pytest test_seam_all -x); `HISTORY#186` was SOP 1-4 handoff docs (SEAM LoCoMo adapter, LLM-judge, Mem0 comparator, Zep comparator) landed on `main` as a docs-only follow-up; PR #24 superseded since its continuity bookkeeping was already covered by PR #25. `HISTORY#185` — SOP 0 of Track I landed `seam bench external` CLI alias, tests expanded 4→12, 188 passed; `HISTORY#184` was audit closeout verified committed and uncommitted state, committed the previously unstaged `HISTORY#183` patch as `8bee677`, pushed `main`, and confirmed the single attached worktree was clean with ahead/behind 0/0 before the #184 bookkeeping entry. `HISTORY#183` fixed MCP import isolation and context-pack refs after follow-up verification found H3 and H5 were not false positives. `HISTORY#182` remains the H-track hardening sweep across 9 parallel audit agents (models thread-safety + retry, MCP traceback logging, reconcile deterministic tie-breaking, memory bounded neighbor lookup, storage stale-edge + orphaned-projection fixes) plus C1-C6 runtime/API scale hardening from #181: query-bounded trace traversal, streaming SQLite vector search top-k, bounded REST request bodies, process-local rate limiter cleanup and multi-worker guardrails, authenticated remote bind refusal without explicit insecure override, and rollback/error surfacing when vector indexing fails after a canonical SQLite write. Prior handoffs: `HISTORY#180` merged PR #23 roadmap concept harvest, `HISTORY#179` salvaged operator/engineering docs, `HISTORY#178` merged PR #22 external memory benchmark roadmap + registry, and `HISTORY#176` captured the open infinite-indexing decision. Track H1 Context Streams substrate is fully implemented and measured; the recorded-fact audit gate is stable (no `--no-recorded-fact-audit` required) after HISTORY#172–#175; all four verify gates pass. Repo-local `.venv` exists with all-extras + pytest; `experimental/webui/node_modules` uses `--no-bin-links` per HISTORY#173 because this filesystem rejects symlinked `.bin` shims. Cross-index hot zone is at the 200-event cap with cold archive chunk `.seam/cross_index_archive/0001-0017.cross.md`. **Open architecture decision for the next session:** the operator asked about an "infinite indexing" system for roadmap + docs + ledgers + source + experience. A `codex-gpt-5` audit (run against a stale tree) proposed a new SQLite `context_index` table; my dissection in HISTORY#176 recommends instead extending H1 → H4 library streams (`tools/streams/library_walker.py` ingesting docs/, docs/roadmap/, docs/ledgers/ by heading + source by AST symbol) and H3 retrieval integration (`build_context_pack --include`, `--layer`, `--around`), populating the existing `projection_index` table for vector acceleration, rather than forking a parallel `context_index`. The operator did not select an approach before requesting handoff; the next session should confirm approach before coding. Path canonicality flip for `history` (root → `.seam/streams/history/`) remains explicitly deferred per CONTEXT_STREAMS.md §9. Benchmark suite work is unblocked whenever the operator wants to switch to it. Snapshot JSON files are local derived artifacts, so a fresh Linux clone should regenerate the resume snapshot with the command in `docs/setup.md` before running continuity verification.
- A fresh Linux clone should run `sh ./installers/install_seam_linux.sh --dev`, then verify local `HEAD` equals `origin/main` before starting new work.
- GitHub PR state as of 2026-05-17: PRs #22, #18, #23, #25 (SOP 0), #26 merged. PR #27 (SOP 1) is in review. SOP 2 (LLM-judge) is next. PRs #22, #18, and #23 are all merged into main (commits `458eca8`, `b059cdb`, `c9bfe2a`). PR #19 is still draft, conflicting, and must be treated as a partial extraction source because its branch contains private-session-link material in commit metadata. PR #24 (Track I 5-SOP handoff series) was draft and is now superseded — the four new SOP markdown files were cherry-picked to a fresh docs-only PR; PR #24 should be closed. PR #25 (SOP 0) merged as commit `8b389d2`. SOP 1 (LoCoMo adapter) is next.
- Next work should continue from the IDE-like web dashboard / REST API GUI, Track H Phase 2-4 (improvement streams, retrieval integration, generalized library streams — design locked in `docs/roadmap/CONTEXT_STREAMS.md`), Track I Phase 2+ (external memory benchmark adapters and `seam bench external` CLI alias), Track L Agent/Skills Compiler (renamed from PR #23's H), Track K Trust/Security/Auditability work, and first-class agent CLI direction. Do not resume from already-merged HS/1 adapter/repair/benchmark branches or stale squash-merged PR refs.

## What Is Stable

- Core runtime paths (compile, verify, persist, search, context, benchmark)
- Textual dashboard (interactive TUI, chat, slash palette, reload command, MIRL animation, independent pane scrolling including Settings and Overview, ExplorerTree navigation, status bar, colored Rich markup panels, focus zoom toggle, Settings tab, and live Overview health bars)
- Dashboard installers: `seam-dash` shim on Windows (`.cmd`) and POSIX; `seam-dash` entrypoint in `pyproject.toml`
- Linux installer modes: `sh ./installers/install_seam_linux.sh` for global user commands, `sh ./installers/install_seam_linux.sh --dev` for repo-local Python development bootstrap and SEAM continuity checks.
- Dashboard launcher: `scripts/windows/launch_dashboard.bat` + `launch_dashboard.ps1`; propagates pgvector config from `SEAM_LOCAL_ENV` or a private Documents `SEAM\local\.env`
- pgvector real adapter: Docker Compose service `seam-pgvector` (image `pgvector/pgvector:0.8.2-pg18-trixie`, port 55432)
- Dashboard snapshot/smoke-test behavior
- Benchmark bundle verification, diff, gate, holdout workflow, and Windows GitHub Actions workflow (see HISTORY#095)
- `seam bench external --plan` CLI alias and `benchmarks/registry/memory_benchmarks.json` registry
- REST API skeleton: `seam serve`, `seam-server`, optional `server` extra, bearer-token protected endpoints, bounded request bodies, env-configurable process-local rate limiting, and remote authenticated bind guardrails
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
- Legacy roadmap entries `HISTORY#028`-`HISTORY#047` remain append-only planning cards. `HISTORY#036` (holdout suites), `HISTORY#037` (benchmark diff tooling), and `HISTORY#046` (REST API surface) are implemented and superseded by `HISTORY#152`, `HISTORY#153`, and `HISTORY#154`; use `ROADMAP.md` Recommended Course for current priority.
- Track H Context Streams Protocol is planned (Phase 1 = H1 now; Phase 2 = H2 deferred ~4 weeks until H1 operational data accumulates). Full design captured in `docs/roadmap/CONTEXT_STREAMS.md`; ready to implement when the operator picks it up. The design generalizes the single-stream history protocol into a multi-stream substrate (history + roadmap + experience + library + improvement) joined by an append-only `cross_index.md`, with the same append-only / supersedes / verify discipline applied uniformly to each stream.

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

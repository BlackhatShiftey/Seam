# SEAM Project Status

Last updated: 2026-05-20 (HISTORY#219 — Live-services audit, pgvector migration + stats bugs surfaced, test env isolation fix, two new SOPs)

## Current State

SEAM is operating as a local machine-first memory runtime with:

- MIRL compile/verify/persist/search/context flows in production use
- External memory benchmark registry + `seam bench external` CLI alias (Track I SOP 0 landed)
- SEAM LoCoMo adapter with string-match scoring + 60s quickstart fixture (Track I SOP 1 landed; `seam bench external --quickstart locomo`)
- Benchmark Integrity Level Phase 1 support: deterministic BIL-0 inspection plus BIL-1/BIL-2 benchmark sealing, verification, and inspection via `seam bench seal|verify|inspect`
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
- IDE-like browser dashboard under `experimental/webui/` now launches the finished static dashboard from `public/dashboard.html` at the Vite root, with `public/seam-api.js` wiring health, stats, compile, search, context, persist, and lossless-compress calls through the local REST API proxy while the TypeScript panes remain rework material.
- Adaptive SEAM Skill Factory foundation is merged on `main` through PR #21; current tracked code includes Skill Factory primitives and roadmap docs under `seam_runtime/skills/` and `docs/roadmap/SKILL_FACTORY.md`.

## Current Resume Point

- `main` is the source-of-truth branch. After pulling, verify local `HEAD` equals `origin/main` before starting new work.
- Latest continuity handoff is `HISTORY#219` — Live-services audit pass with the "never skip tests, launch everything" rule. With docker pgvector reachable and SEAM_PGVECTOR_DSN exported, the full suite `pytest test_seam_all/ tools/history/test_history_tools.py tools/streams/ tests/` ran 467 passed, 0 skipped, 3 subtests; all 4 SEAM verify gates green. Three real bugs surfaced that #218 missed: (1) pgvector schema migration is missing for #218's composite-PK change — `create table if not exists` is a no-op on existing tables, so any pre-#218 pgvector deployment breaks with `InvalidColumnReference` on insert (P0, documented in `docs/SOP_BENCHMARKABLE_STATE_ROADMAP.md`); (2) `SQLiteStore.get_stats()["vector_entries"]` always queries the SQLite vector_index table even under pgvector, so dashboard/stats/doctor report 0 (P1, documented); (3) `SeamTests.setUp` did not isolate from operator `SEAM_PGVECTOR_DSN`, causing 2 tests to fail under the real backend (P0b, fixed inline in `test_seam_all/test_seam.py:82-96`). Two new SOPs landed: `docs/SOP_CRITICAL_BENCHMARKABILITY_FIX.md` (minimal LoCoMo adapter patch — evidence-closure + pack_ir mode=exact) and `docs/SOP_BENCHMARKABLE_STATE_ROADMAP.md` (sequenced execution to a real comparator baseline). HISTORY#218 (parallel audit remediation across 7 lanes) was the prior handoff. 10 new audit test files. The SOP is `docs/SOP_DEEPSEEK_PARALLEL_AUDIT_EXECUTION.md`. `HISTORY#217` is the prior Track K BIL repair. `HISTORY#216` is Stage 1 tokenizer unification.
- A fresh Linux clone should run `sh ./installers/install_seam_linux.sh --dev`, then verify local `HEAD` equals `origin/main` before starting new work.
- GitHub PR state as of 2026-05-18: PRs #22, #18, #23, #25 (SOP 0), #26, #27 (SOP 1), #28 (SOP 2), #29 (SOPs 3+4), and #30 (production readiness remediation) merged. Track I (SOPs 0-4) is complete on `main`. PR #19 is still draft, conflicting, and must be treated as a partial extraction source because its branch contains private-session-link material in commit metadata. PR #24 (Track I 5-SOP handoff series) was draft and is superseded.
- **Track I COMPLETE milestone.** Next track is the operator's choice per ROADMAP.md: Track J (Prompt Codec), Track K (Trust/Security/Auditability + BIL bundles), Track L (Agent/Skills Compiler), or Track H Phase 2-4 (improvement streams, retrieval integration, generalized library streams). Do not resume from already-merged branches or stale squash-merged PR refs. Do not propose or start Tracks J/K/L without operator direction.

## What Is Stable

- Core runtime paths (compile, verify, persist, search, context, benchmark)
- Textual dashboard (interactive TUI, chat, slash palette, reload command, MIRL animation, independent pane scrolling including Settings and Overview, ExplorerTree navigation, status bar, colored Rich markup panels, focus zoom toggle, Settings tab, and live Overview health bars)
- Dashboard installers: `seam-dash` shim on Windows (`.cmd`) and POSIX; `seam-dash` entrypoint in `pyproject.toml`
- Linux installer modes: `sh ./installers/install_seam_linux.sh` for global user commands, `sh ./installers/install_seam_linux.sh --dev` for repo-local Python development bootstrap and SEAM continuity checks.
- Dashboard launcher: `scripts/windows/launch_dashboard.bat` + `launch_dashboard.ps1`; propagates pgvector config from `SEAM_LOCAL_ENV` or a private Documents `SEAM\local\.env`
- pgvector real adapter: Docker Compose service `seam-pgvector` (image `pgvector/pgvector:0.8.2-pg18-trixie`, port 55432)
- Dashboard snapshot/smoke-test behavior
- Benchmark bundle verification, diff, gate, holdout workflow, and Windows GitHub Actions workflow (see HISTORY#095)
- Benchmark Integrity Level Phase 1 workflow: `seam bench inspect` reports BIL-0 for raw benchmark results, `seam bench seal --level BIL-1|BIL-2` writes deterministic bundles, and `seam bench verify` checks stable result hashes, BIL-2 manifest hashes, and BIL-2 manifest/result consistency. Stub-judge results require explicit `--allow-stub-seal` above BIL-0.
- `seam bench external --plan` CLI alias and `benchmarks/registry/memory_benchmarks.json` registry
- External memory benchmark suite (Track I complete): `seam bench external --quickstart locomo` with `--adapter {seam|mem0|zep}` and `--judge {stub|claude|openai}`; Mem0 comparator behind `seam[bench-mem0]` optional extra; Zep comparator behind `seam[bench-zep]` optional extra; three-way SEAM/Mem0/Zep scoring reproducible on quickstart fixture
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

- Deferred: ~113 remaining assertTrue→specific-assertion replacements in test_seam.py (backlog card roadmap:track:F:asserttrue-scrub)
- Deferred: 10 low-priority backlog items catalogued under Track F (Phase 7)
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

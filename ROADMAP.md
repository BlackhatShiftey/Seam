# SEAM Improvement Roadmap & SOP Blueprint

**Last updated:** 2026-04-20
**Status:** Active planning document. This is the living roadmap for SEAM development beyond the stable v1 core.

---

## Track A0 — True Interactive TUI (foundation for all UI work)

### A0: Migrate Dashboard to Textual — Live Panels, In-Place Input, Scrollable Boxes

**What:** Replace the current Rich-based re-render loop with a proper interactive TUI using **Textual**. The dashboard becomes a persistent session: input is handled at the bottom of the screen in-place, panels update reactively without flashing or reprinting, and every data panel is independently scrollable within its bordered box. A `seam-dash` CLI entrypoint launches it directly.

**Why first:** Every other Track A item (animations, graphs, chat tab, presentation mode) is easier and cleaner to build on a proper TUI framework than on top of a re-render loop. This is the foundation.

**How:**
- Migrate from `Rich.Live` full-screen re-render → **Textual** widgets with reactive data bindings
- Each panel becomes a Textual `DataTable`, `ListView`, or custom `ScrollView` widget — independently scrollable
- Input bar at the bottom is a Textual `Input` widget; on submit it runs the existing `execute()` logic and updates only the affected panel
- Add `seam-dash = "seam_runtime.dashboard:main"` to `[project.scripts]` in `pyproject.toml`
- Keep `seam dashboard` as an alias; keep `--snapshot` (headless) mode working throughout

**Panels that get independent scroll:**
- Memory Records
- Search / Retrieval Results
- Benchmark Results
- Runtime Log / Event stream
- Chat (when Track A5 lands)

**SOP:**
1. Add `textual>=0.50` as optional extra (`seam-runtime[dash]`) or promote to base if dashboard is a primary interface
2. Port existing panels to Textual widgets one at a time — keep snapshot fallback working at every step
3. Wire `Input` widget at bottom; results update the relevant panel reactively
4. Add `seam-dash` console entrypoint to `pyproject.toml`
5. Test: `--snapshot` headless export must still pass; add ≥3 Textual widget tests
6. Gate: no full-screen flash on any input; all panels scroll independently; works on Windows terminal and Linux/WSL2

---

## Track A — Dashboard & UI Enhancement
History pointer: see `HISTORY#047` (interactive TUI baseline) and `HISTORY#024` (dashboard review stabilization).

### A1: NL→MIRL Compilation Animation

**What:** When a user runs `compile <text>` in the dashboard, show a live animation of the compilation process — text being parsed, records appearing one by one with their type labels (ENT, CLM, REL, ACT, OBJ) before the final summary.

**How:**
- Use Rich `Live` context manager in `dashboard.py`
- On compile, stream record creation events from `compile_nl` by yielding intermediate batches
- Each record appears with a typewriter-style pop: `[green]ENT[/green] ent:project:seam → "SEAM"`
- Final frame shows the full compiled batch summary

**SOP:**
1. Add a `compile_nl_streaming` variant or hook to `seam_runtime/nl.py` that yields records as they are produced
2. Wire the stream into `DashboardApp.execute` for the compile command
3. Render each yield step via `Rich.Live` with a short frame delay (50ms)
4. Write a `--snapshot` test that captures the final frame

**Gate:** Animation must not break `--snapshot` mode or scripted `run_script` execution.

---

### A2: Benchmark Progress Bar & Live Metrics

**What:** During `seam benchmark run all`, show a live progress bar with per-family status, current scores, and elapsed time — not just a final JSON dump.

**How:**
- Rich `Progress` with one task per benchmark family
- Live-update recall@k, token savings, and pass/fail as each case completes
- Final frame shows the summary table

**SOP:**
1. Add an optional `progress_callback` parameter to `run_benchmark_suite` in `benchmarks.py`
2. Wire it into the CLI and dashboard benchmark command
3. Dashboard: use `Rich.Live` wrapping a `Progress` + results table

**Gate:** Must not change the benchmark output bundle format or break `benchmark verify`.

---

### A3: Benchmark History Graphs (ASCII sparklines)

**What:** In the Benchmark tab, show a sparkline graph of recall@k and token savings across the last N stored runs, so you can see whether the system is improving or regressing over time.

**How:**
- Query `benchmark_runs` table from SQLite for last 10 runs
- Compute per-family summary metrics per run
- Render as ASCII sparklines using a lightweight library (`sparklines`, `plotext`, or hand-rolled)
- Show in the Benchmark tab's third panel column

**SOP:**
1. Add a `load_benchmark_history(limit)` helper to `storage.py`
2. Add `_build_benchmark_history_graph()` to `DashboardApp`
3. Swap it into the Benchmark tab layout alongside the existing summary table
4. Sparkline renders as a single Rich `Text` object — no external rendering dependency

**Gate:** Must work with zero runs (show empty state gracefully) and with 1+ runs.

---

### A4: Vector Space Visualization

**What:** A new `vectors` command in the dashboard (or a standalone `seam vectors` CLI command) that projects stored embeddings to 2D using UMAP or t-SNE and renders a scatter plot colored by record kind.

**Do we need a separate tool?** No — but it needs optional dependencies. The projection math (`umap-learn` or `scikit-learn` for t-SNE) is heavy. Keep it behind an optional extra (`seam-runtime[viz]`). The rendering can be ASCII (via `plotext`) in the terminal or HTML canvas via a web artifact.

**How:**
1. Add `viz` optional extra to `pyproject.toml`: `umap-learn>=0.5`, `plotext>=5.0`
2. Add `seam_runtime/viz.py`: load vectors from SQLite, run UMAP, return 2D coordinates + kind labels
3. Add `vectors` command to dashboard and CLI
4. Render: ASCII scatter via `plotext` for terminal; HTML canvas artifact for richer view

**SOP:**
1. Implement `viz.py` with graceful `ImportError` guard (same pattern as `rich` guard)
2. Add `vectors` command to `_build_command_parser` in `DashboardApp`
3. ASCII render first; HTML artifact as a follow-on
4. Test: mock the embedding data, assert 2D projection output shape

**Gate:** Must degrade gracefully if `umap-learn` is not installed — show a clear install hint.

---

### A5: Chat Tab with Claude Model

**What:** Add a `Chat` tab to the dashboard. The user types a message; SEAM retrieves relevant context from the DB; the context + message is sent to Claude API; the response appears in the result panel. The model can also invoke SEAM operations as tool calls.

**How:**
- New tab: `runtime | benchmark | chat`
- Chat history stored in `DashboardApp` as a deque
- On each message: run `search_ir` + `pack_ir` to get context, send as system prompt to Claude
- Claude can call tools: `compile`, `search`, `context`, `stats`
- Response streamed into the result panel via Rich `Live`

**Required:** `anthropic` SDK installed. Add `chat` optional extra to `pyproject.toml`.

**SOP:**
1. Add `chat` optional extra: `anthropic>=0.40`
2. Add `_build_chat_context(query)` to `DashboardApp` — retrieves and packs relevant records
3. Add `ChatSession` dataclass: messages list, tool definitions
4. Add `chat` command to parser; wire into `execute()`
5. Define SEAM tools for Claude: `seam_search`, `seam_compile`, `seam_context`, `seam_stats`
6. Render streamed response using Rich `Live`
7. Add `Chat` tab to header tab switcher

**Gate:** Must not require `anthropic` for any non-chat operation. Chat tab shows "anthropic not installed — run pip install seam-runtime[chat]" if missing.

---

### A6: Dashboard as a Benchmarking Presentation Tool

**What:** A `--present` mode for the dashboard that locks into full-screen benchmark display — large metrics, color-coded pass/fail cells, animated score bars — suitable for showing SEAM benchmark results in a demo or presentation context.

**How:**
- `seam dashboard --present` launches in presentation mode
- Full terminal width used for benchmark summary table with large text
- Scores animate from 0 to actual value on load (progress bar fill)
- Auto-refreshes every 30s from the latest persisted run

**SOP:**
1. Add `--present` flag to the dashboard CLI parser
2. Add `run_presentation()` method to `DashboardApp`
3. Build a `_build_presentation_layout()` that uses Rich `Table` with larger cells and styled score columns
4. Auto-refresh: use `Rich.Live` with `refresh_per_second=0.033` (30s equivalent via manual control)

---

## Track B — Command Terminology & README Refinement
History pointer: see `HISTORY#002`, `HISTORY#024`, `HISTORY#033`.

### B1: Command Naming Audit

**Current problems:**
- `compile-nl` / `compile-dsl` — "compile" is developer-speak for a memory tool
- `lossless-compress` / `compress-doc` — redundant aliases with inconsistent style
- `promote-symbols` — vague; users don't know what "promote" means here
- `rag-sync` / `rag-search` — internal jargon leaking into the surface
- `transpile` — very developer-specific
- `reconcile` — ambiguous to non-developers

**Proposed theme: "SEAM as a knowledge operating system"**

All commands should feel like natural operations on a memory system:

| Current | Proposed | Rationale |
|---|---|---|
| `compile-nl` | `remember` or `learn` | User is teaching SEAM something |
| `compile-dsl` | `script` | DSL is structured input — scripting feels right |
| `persist` | `store` | Plain English |
| `search` | `find` | Intuitive |
| `retrieve` | `fetch` | Consistent with find |
| `lossless-compress` | `compress` | Single clean verb |
| `lossless-decompress` | `restore` | Paired with compress |
| `promote-symbols` | `mint` | Symbols are being created/promoted into the system |
| `reconcile` | `sync` | Aligns state |
| `transpile` | `convert` | Plain English |
| `context` | keep | Already good |
| `pack` | keep | Already good |
| `doctor` | keep | Already great |
| `dashboard` | keep | Already great |

**SOP:**
1. Add new names as primary commands; keep all existing names as compatibility aliases
2. Update `--help` text to use the new names first, aliases in parentheses
3. Update `installers/README.md` and `CLAUDE.md` to use new names
4. Do NOT remove aliases — external scripts and muscle memory should never break
5. Gate: all existing tests pass unchanged (aliases still work)

---

### B2: Argument Consistency Pass

**Current problems:**
- `--vector-backend` / `--semantic-backend` are the same flag with two names
- `--vector-path` / `--chroma-path` — leaks Chroma implementation detail
- `--pack-budget` vs `--budget` — inconsistent naming across commands
- `--min-savings` only appears in some benchmark commands

**Proposed fixes:**
- Consolidate to `--backend` (seam|chroma|pgvector) with `--semantic-backend` as alias
- Rename `--vector-path` → `--backend-path`
- Standardize `--budget` everywhere
- Document all flags in a single reference section in `installers/README.md`

---

### B3: README Consolidation

**Current state:** There are multiple README files (`installers/README.md`, `benchmarks/README.md`, `experimental/retrieval_orchestrator/README.md`) with overlapping and sometimes stale content.

**SOP:**
1. Audit all README files for stale content
2. Make `installers/README.md` the operator-facing entry point (install + quickstart)
3. Move benchmark operator docs to `benchmarks/README.md`
4. Move retrieval architecture docs to `experimental/retrieval_orchestrator/README.md`
5. Add a root-level `README.md` that links to all of the above

---

## Track C — Benchmark Hardening
History pointer: see `HISTORY#008`, `HISTORY#011`, and planned benchmark hardening items `HISTORY#036`-`HISTORY#040`.

### C1: Holdout Suites

**What:** Cases that were never used during development and are only run at publish time. Results from holdout suites are the only ones that count as external claims.

**Status:** Implemented 2026-04-27. See `HISTORY#092`.

**SOP:**
1. `benchmarks/fixtures/holdout/` exists and local JSON files are ignored by git
2. `seam benchmark run --holdout` only loads fixtures from that directory
3. `--holdout` requires an interactive confirmation or `--confirm-holdout`
4. Default holdout JSON bundles are stored separately under `benchmarks/runs/holdout/`

---

### C2: Benchmark Diff Tooling

**What:** `seam benchmark diff <run-a.json> <run-b.json>` — shows a structured delta between two runs: which cases improved, which regressed, by how much.

**Status:** Implemented 2026-04-27. See `HISTORY#092`.

**SOP:**
1. Use `seam benchmark diff <run-a> <run-b>` with bundle paths or persisted run ids
2. The diff verifies both bundles, joins exact matches on case hash, and falls back to `family::case_id` when the case hash changed
3. Numeric and boolean metrics get per-case deltas with green/red/gray indicators
4. JSON and pretty output include summary counts for improvements, regressions, added cases, and removed cases

---

### C3: Gold Standard Benchmarks

**What:** Run SEAM's retrieval engine against publicly known benchmarks to get externally comparable numbers.

**Target benchmarks:**
- **BEIR** (Benchmarking IR): 18 diverse retrieval tasks — covers fact retrieval, argument mining, biomedical, financial
- **MTEB** (Massive Text Embedding Benchmark): evaluates embedding quality across classification, clustering, retrieval
- **MS-MARCO**: passage ranking at scale

**SOP:**
1. Add `benchmarks/external/` directory for gold standard fixture adapters
2. Write a BEIR adapter that converts BEIR datasets into SEAM retrieval fixtures
3. Run SEAM's hybrid retrieval (SQLite + SBERT) against BEIR tasks
4. Store results in `benchmarks/runs/` with a `source=beir` tag
5. Document results in `benchmarks/BENCHMARK_LOG.md`

**Note:** This requires downloading BEIR datasets (~GB scale). Keep adapters separate from the main fixture suite.

---

### C4: Adversarial Testing

**What:** Deliberately try to break SEAM — malformed MIRL, adversarial queries, very long documents, Unicode edge cases, concurrent writes, empty databases.

**SOP:**
1. Add `benchmarks/fixtures/adversarial/` with edge-case inputs
2. Write an `adversarial` benchmark family in `benchmarks.py`
3. Each case should either pass cleanly or fail with a specific known error — no silent corruption
4. Target: 100% cases either pass or raise a documented exception

---

### C5: Cross-Machine Reproducibility

**What:** The same benchmark run on Windows and Linux should produce identical scores.

**SOP:**
1. Add a `reference_run.json` to the repo as a locked reference
2. `seam benchmark verify --reference reference_run.json` checks current scores against reference within a tolerance
3. CI-equivalent: run this check before any claim of benchmark improvement

---

## Track D — Model Skills & Automation
History pointer: see `HISTORY#041`-`HISTORY#043`.

### D1: SEAM as Claude Tool Set

**What:** Define SEAM operations as Claude tool_use functions so a Claude agent can use SEAM's memory as a live knowledge base during a conversation.

**Tools to define:**
- `seam_compile(text: str) → IRBatch` — compile and persist natural language
- `seam_search(query: str, budget: int) → SearchResult` — retrieve relevant records
- `seam_context(query: str) → Pack` — get a generation-ready context pack
- `seam_compress(text: str) → LosslessArtifact` — compress to machine text
- `seam_stats() → dict` — runtime health and record counts

**SOP:**
1. Create `seam_runtime/tools.py` — defines tool schemas as Anthropic tool_use dicts
2. Add `SeamToolExecutor` class that maps tool_name → runtime method call
3. Wire into the dashboard Chat tab (Track A5)
4. Document as a standalone integration guide

---

### D2: Auto-Compression Pipeline

**What:** A background process (or CLI command) that watches a directory, compresses new files with SEAM-LX/1, and persists the MIRL to the database automatically.

**SOP:**
1. Add `seam watch <directory>` command to CLI
2. Use `watchdog` library (new optional extra) to monitor file events
3. On new/modified file: compress → compile-nl → persist → index
4. Log each operation to a watch log in SQLite
5. Add `seam watch --once` for a single-pass scan without ongoing watch

---

### D3: Batch Compile

**What:** `seam batch-compile <glob>` — compile and persist multiple files at once with a progress bar and summary report.

**SOP:**
1. Add `batch-compile` command to CLI
2. Accept a glob pattern or directory
3. Process files in parallel using `concurrent.futures.ThreadPoolExecutor`
4. Show Rich progress bar; write a summary JSON on completion
5. Gate: test with 1 file, 10 files, and an empty glob

---

## Track E — Architecture & Scalability
History pointer: see `HISTORY#012`, `HISTORY#019`, and planned scale tracks `HISTORY#044`-`HISTORY#046`.

### E1: PgVector as Configurable Default

**What:** When `SEAM_PGVECTOR_DSN` is set, PgVector is already used automatically. The next step is making it the explicit recommended backend for deployments with >10k records, and adding a migration path from SQLite vector index to PgVector.

**SOP:**
1. Add `seam migrate-vectors --to pgvector` command
2. Reads all vector embeddings from SQLite vector_index, writes them to PgVector
3. Verifies row counts match before and after
4. Marks the migration in a `migrations` table so it's idempotent

---

### E2: Multi-Tenant Namespacing

**What:** SEAM already has namespaces (`ns`) and scopes (`scope`) on records. The next step is enforcing tenant isolation at the API level — a `tenant_id` that gates all queries.

**SOP:**
1. Add `tenant_id` column to `ir_records` and related tables (migration)
2. Add `--tenant` flag to all CLI commands
3. All queries filter by tenant_id unless `--all-tenants` is passed (operator-only)
4. Test: two tenants with overlapping record IDs — queries must not cross-contaminate

---

### E3: REST API Surface

**What:** Expose SEAM operations as a lightweight HTTP API so external systems can compile, search, and retrieve without running a full Python process.

**Status:** Implemented 2026-04-27. See `HISTORY#094`.

**SOP:**
1. `seam serve` runs FastAPI/Uvicorn through the optional `server` extra.
2. Endpoints: `POST /compile`, `POST /compile-dsl`, `GET /search`, `POST /context`, `POST /lossless-compress`, `POST /persist`, `GET /stats`, `GET /health`.
3. Auth: Bearer token through `SEAM_API_TOKEN` for protected endpoints.
4. Rate limiting: `SEAM_API_RATE_LIMIT_PER_MINUTE` or `SEAM_API_RATE_LIMIT`; `/health` is unauthenticated but still rate-limited.
5. Tests: FastAPI `TestClient` coverage for auth, compile/search/context/stats, and rate limiting.

---

## Track F — Docs, Setup Guides, and Error Playbooks

### F1: Operator Setup Guide with Exact Commands

**What:** Publish a single setup guide with exact copy/paste commands for Windows, Linux, and WSL2, including optional extras and verification commands.

**SOP:**
1. Add `docs/setup.md` with exact command blocks for:
   - creating virtual env
   - installing base deps
   - installing extras (`[dash]`, `[pgvector]`, `[sbert]`, `[all-extras]`)
   - running smoke checks (`seam doctor`, `seam dashboard --snapshot`, benchmark smoke)
2. Add a short "known good first run" section with expected command output fragments.
3. Link `docs/setup.md` from root `README.md` and `installers/README.md`.
4. Gate: a clean machine can reach `seam doctor: PASS` by following only this doc.

---

### F2: Documented Error Catalog and Fix Procedures

**What:** Create a troubleshooting catalog that maps common operator errors to exact recovery steps.

**SOP:**
1. Add `docs/errors.md` with one section per documented error:
   - symptom text (exact error snippets)
   - root cause
   - fix commands
   - verification command after fix
2. Include current high-frequency paths:
   - missing optional dependency (Textual/PgVector/SBERT)
   - pgvector DSN configured but unreachable
   - Chroma path/index sync failures
   - benchmark bundle verification failures
3. Add "do not proceed" blockers and escalation steps.
4. Gate: each documented error has at least one reproducible verification command.

---

### F3: How-To Runbooks for Daily Operations

**What:** Add task-oriented runbooks for common operator workflows so users can execute standard flows without source code spelunking.

**SOP:**
1. Add `docs/howto/` with runbooks:
   - ingest and retrieve memory
   - run guarded real-adapter checks
   - archive benchmark bundles to Documents
   - recover from interrupted runs
2. Keep runbooks command-first with short explanation blocks.
3. Add a top-level index file `docs/howto/README.md`.
4. Gate: every runbook has prerequisites, exact commands, and a success checklist.

---

## Recommended Course — Priority Order

Work these in sequence. Each track has a clear gate before moving on.

```
Phase 1 (Now — foundational polish)
├── B1: Command naming audit + aliases
├── B3: README consolidation
└── C2: Benchmark diff tooling (done; see HISTORY#092)

Phase 2 (Dashboard enhancement)
├── A2: Benchmark progress bar
├── A3: ASCII sparkline graphs
├── A1: NL→MIRL compilation animation
└── A6: Presentation mode

Phase 3 (Benchmark credibility)
├── C1: Holdout suites (done; see HISTORY#092)
├── C5: Cross-machine reproducibility
├── C4: Adversarial testing
└── C3: Gold standard benchmarks (BEIR/MTEB)

Phase 4 (Model integration)
├── D1: SEAM as Claude tool set
├── A5: Chat tab in dashboard
└── D2: Auto-compression pipeline

Phase 5 (Scalability)
├── D3: Batch compile
├── A4: Vector visualization
├── E1: PgVector migration helper
└── E3: REST API surface

Phase 6 (Architecture)
└── E2: Multi-tenant namespacing
```

---

## SOP: Approach Rules for Every Track

These rules apply to every piece of work on this repo, regardless of track.

1. **Tests before merge.** Every new feature needs at least one test before it lands. No exceptions.

2. **No benchmark claims without bundle verification.** Any improvement to retrieval or compression must be backed by a verified JSON bundle in `benchmarks/runs/`.

3. **SQLite stays canonical.** PgVector, Chroma, and any future vector store are derived retrieval layers. The source of truth is always SQLite.

4. **Aliases before removals.** When renaming a command, add the new name and keep the old as an alias. Only remove old names after a deprecation cycle with a warning.

5. **Optional extras for heavy dependencies.** ML libraries, Postgres drivers, watch daemons — all go behind optional extras. The base install must stay lean.

6. **Update the ledger.** Every session that changes direction or completes a milestone must update `REPO_LEDGER.md` and `PROJECT_STATUS.md`.

7. **Handoff block.** Every session that ends mid-work must leave a handoff block in `REPO_LEDGER.md` so the next Claude session can resume without re-reading the full conversation.

8. **Lossless is sacred.** The lossless roundtrip must always pass SHA-256 verification. Any change to compression/decompression must re-run `seam demo lossless` and verify the output.

9. **Doctor must pass.** After any install-path change, `seam doctor` must return PASS. If it doesn't, that's a blocker.

10. **Benchmark diff before claiming improvement.** Use `seam benchmark diff` before publishing any improvement claim. Numbers alone are not enough — show the delta.

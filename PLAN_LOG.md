# SEAM Plan Log

This file is append-only. Never delete or edit existing entries.
Each plan gets logged when it is set, updated when its status changes, and annotated when it is finished or abandoned.
Over time this file becomes the historical record of what was planned, what changed, and what was actually built.

For the current active roadmap see: `ROADMAP.md`
For engineering history and milestone entries see: `REPO_LEDGER.md`

---

## How to Use

- When a new plan is made → add a `[PLANNED]` entry under the current date
- When work begins → add a `[IN PROGRESS]` note below the plan entry
- When a plan is finished → add a `[DONE]` note with the date and commit/result
- When a plan changes scope or is deferred → add a `[CHANGED]` or `[DEFERRED]` note explaining why
- When a plan is abandoned → add `[ABANDONED]` with a reason — never delete the original

---

## Log

### 2026-04-17

#### [DONE] Core runtime: compile → verify → persist → search → pack
Set and executed across sessions 1–10.
- `compile-nl` and `compile-dsl` produce MIRL
- verification, SQLite persistence, vector indexing all working
- search, trace, pack, reconcile, transpile, and symbol export all working
Finished: 2026-04-17

---

#### [DONE] Retrieval and context pipeline
Set: early project planning.
- retrieval planning, structured + vector retrieval legs
- merged ranking, context/RAG pack generation
- `context` views: pack, prompt, evidence, summary, exact-record
- SQLite leg with SQL-side filtering and ranking
- Chroma as optional semantic backend
Finished: 2026-04-17

---

#### [DONE] SEAM-LX/1 lossless compression
Set: step 8 planning.
- exact machine-text envelope with SHA-256 integrity verification
- lossless loop searches reversible transforms/codecs
- fluctuation/regression logging for debugging
- `seam demo lossless` one-command flow verified
Finished: 2026-04-17

---

#### [DONE] Six-family benchmark engine
Set: step 9 planning.
- families: lossless, retrieval, embedding, long_context, persistence, agent_tasks
- bundles with case hashes, bundle hashes, fixture hashes
- persisted run history in SQLite
- `seam benchmark run`, `show`, `verify` all working
- tokenizer-aware reporting with tiktoken + fallback
Finished: 2026-04-17

---

#### [DONE] SBERT retrieval — machine-text projection validation
Set: step 12 planning.
- SBERT-based semantic retrieval tested against machine-text projections
- 100% recall proven across all tracks (cross-domain gap closed)
- confirms machine-projection architecture is viable for production
Finished: 2026-04-17

---

#### [DONE] PgVector backend — formal testing and env-var support
Set: 2026-04-17 session.
- `FakePgVectorAdapter` test pattern for offline testing
- 6 PgVector adapter tests added to test suite
- `SEAM_PGVECTOR_DSN` env var pickup in `runtime.py`
- `seam doctor` now reports PgVector status + psycopg/sentence_transformers deps
- 62 tests green
Finished: 2026-04-17

---

#### [DONE] Optional extras in pyproject.toml
Set: 2026-04-17 session.
- `pgvector`, `sbert`, `all-extras` optional groups added
- base install stays lean — no heavy ML deps by default
Finished: 2026-04-17

---

#### [DONE] Windows installer — end-to-end verification
Set: early project planning.
- `seam` and `seam-benchmark` packaged console commands
- `seam doctor` smoke test
- Windows installer verified end to end: command launch, persistence, lossless demo, dashboard
Finished: 2026-04-17

---

#### [DONE] Linux installer — end-to-end verification
Set: 2026-04-17 session.
- Fixed CRLF line endings in `install_seam_linux.sh` (dash rejected `set -eu` with CRLF)
- Added `.gitattributes` to enforce `*.sh eol=lf` permanently
- Documented `python3.12-venv` as a prerequisite
- Confirmed full install on Ubuntu WSL2 (Python 3.12.3): `seam --help`, `seam dashboard`, persistent DB, all panels
Finished: 2026-04-17

---

### 2026-04-18

#### [DONE] Dashboard review pass (step 15)
Set: 2026-04-18 session, from user request to review and improve the dashboard.
- Removed misleading `Vector Store Path` (was showing `.seam_chroma` even when Chroma not in use)
- Added `Vector Adapter` row (sqlite-vector or pgvector)
- Added `PgVector DSN` status row
- Fixed execution mode: `local (neural)` for SBERT
- Commands panel rebuilt as two-column table
- Header cleaned up with highlighted tab buttons
Finished: 2026-04-18
Commit: `a41a9bc`

---

#### [DONE] Comprehensive ledger update + next-session handoff block
Set: 2026-04-18 session.
- Updated `REPO_LEDGER.md` with all session milestones
- Added handoff block at end of ledger for next Claude session
- Covers: last commits, stable features, next priorities, key files, rules
Finished: 2026-04-18
Commit: `cbc6aa4`

---

#### [DONE] ROADMAP.md — multi-track improvement plan with SOP
Set: 2026-04-18 session, from user request for recommended course + SOP blueprint.
- Track A: Dashboard & UI (animations, graphs, chat tab, presentation mode)
- Track B: Command terminology refinement
- Track C: Benchmark hardening (holdout, diff, BEIR/MTEB, adversarial)
- Track D: Model skills & automation (Claude tool set, auto-compression, batch compile)
- Track E: Architecture & scalability (PgVector migration, multi-tenant, REST API)
- 6-phase priority-ordered sequence
- 10 SOP rules that apply to every track
Finished: 2026-04-18
Commit: `cbc6aa4`

---

#### [DONE] PLAN_LOG.md — append-only plan history file
Set: 2026-04-18 session, from user request to keep a permanent record of all plans.
- Seeded with all plans from project start through 2026-04-18
- Append-only: never delete, never edit existing entries
Finished: 2026-04-18

---

#### [PLANNED] Dashboard animations — NL→MIRL compilation animation
Set: 2026-04-18. See `ROADMAP.md` Track A1.
- Rich `Live` streaming of record creation during `compile`
- Typewriter-style pop for each ENT/CLM/REL/ACT record
- Must not break `--snapshot` mode
Status: not started

---

#### [PLANNED] Dashboard — benchmark progress bar & live metrics
Set: 2026-04-18. See `ROADMAP.md` Track A2.
- Rich `Progress` per benchmark family during `benchmark run`
- Live recall@k, token savings, pass/fail as each case completes
Status: not started

---

#### [PLANNED] Dashboard — ASCII sparkline benchmark history graphs
Set: 2026-04-18. See `ROADMAP.md` Track A3.
- Query last 10 benchmark runs from SQLite
- Render per-family recall@k and token savings as sparklines
Status: not started

---

#### [PLANNED] Dashboard — Chat tab with Claude model
Set: 2026-04-18. See `ROADMAP.md` Track A5.
- New `chat` tab: user types query → SEAM retrieves context → Claude responds
- Claude can invoke SEAM tools: compile, search, context, stats
- Requires `anthropic` SDK optional extra
Status: not started

---

#### [PLANNED] Dashboard — presentation mode (`--present`)
Set: 2026-04-18. See `ROADMAP.md` Track A6.
- Full-screen benchmark display with animated score bars
- Auto-refresh from latest persisted run
Status: not started

---

#### [PLANNED] Vector space visualization
Set: 2026-04-18. See `ROADMAP.md` Track A4.
- Project stored embeddings to 2D via UMAP or t-SNE
- ASCII scatter via `plotext` in terminal
- Optional extra: `seam-runtime[viz]`
Status: not started

---

#### [PLANNED] Command terminology audit & thematic naming
Set: 2026-04-18. See `ROADMAP.md` Track B1.
- Proposed theme: SEAM as a knowledge operating system
- `compile-nl` → `remember`, `search` → `find`, `compress` → `compress`, etc.
- Keep all existing names as compatibility aliases
Status: not started

---

#### [PLANNED] Argument consistency pass
Set: 2026-04-18. See `ROADMAP.md` Track B2.
- Consolidate `--vector-backend` / `--semantic-backend` → `--backend`
- Standardize `--budget` everywhere
Status: not started

---

#### [PLANNED] README consolidation
Set: 2026-04-18. See `ROADMAP.md` Track B3.
- `installers/README.md` → operator entry point
- `benchmarks/README.md` → benchmark operator docs
- Root `README.md` → index linking all docs
Status: not started

---

#### [PLANNED] Holdout benchmark suites
Set: 2026-04-18. See `ROADMAP.md` Track C1.
- Cases never used during development
- `--holdout` flag gates publish-only runs
- Separate `benchmark_holdout_runs` table in SQLite
Status: not started

---

#### [PLANNED] Benchmark diff tooling
Set: 2026-04-18. See `ROADMAP.md` Track C2.
- `seam benchmark diff <run-a.json> <run-b.json>`
- Per-case delta with green/red improvement/regression columns
Status: not started

---

#### [PLANNED] Gold standard benchmarks (BEIR / MTEB / MS-MARCO)
Set: 2026-04-18. See `ROADMAP.md` Track C3.
- BEIR: 18 diverse retrieval tasks
- MTEB: embedding quality evaluation
- Adapters in `benchmarks/external/`
Status: not started

---

#### [PLANNED] Adversarial testing suite
Set: 2026-04-18. See `ROADMAP.md` Track C4.
- Malformed MIRL, adversarial queries, Unicode edge cases, concurrent writes
- `benchmarks/fixtures/adversarial/`
Status: not started

---

#### [PLANNED] Cross-machine reproducibility checks
Set: 2026-04-18. See `ROADMAP.md` Track C5.
- `reference_run.json` locked in repo
- `seam benchmark verify --reference` checks scores within tolerance
Status: not started

---

#### [PLANNED] SEAM as Claude tool set
Set: 2026-04-18. See `ROADMAP.md` Track D1.
- Define SEAM ops as Anthropic tool_use functions
- `seam_compile`, `seam_search`, `seam_context`, `seam_compress`, `seam_stats`
- `seam_runtime/tools.py` with `SeamToolExecutor`
Status: not started

---

#### [PLANNED] Auto-compression pipeline (`seam watch`)
Set: 2026-04-18. See `ROADMAP.md` Track D2.
- Watch a directory → compress new files → compile-nl → persist → index
- `watchdog` optional extra
Status: not started

---

#### [PLANNED] Batch compile (`seam batch-compile <glob>`)
Set: 2026-04-18. See `ROADMAP.md` Track D3.
- Parallel file processing via `ThreadPoolExecutor`
- Rich progress bar + summary JSON
Status: not started

---

#### [PLANNED] PgVector migration helper
Set: 2026-04-18. See `ROADMAP.md` Track E1.
- `seam migrate-vectors --to pgvector`
- Reads SQLite vector_index, writes to PgVector, verifies row counts
Status: not started

---

#### [PLANNED] Multi-tenant namespacing
Set: 2026-04-18. See `ROADMAP.md` Track E2.
- `tenant_id` column on `ir_records` and related tables
- `--tenant` flag on all CLI commands
Status: not started

---

#### [PLANNED] REST API surface (`seam serve`)
Set: 2026-04-18. See `ROADMAP.md` Track E3.
- FastAPI + uvicorn optional extra
- Endpoints: `/compile`, `/search`, `/context`, `/stats`, `/health`
- Bearer token auth via env var
Status: not started

---

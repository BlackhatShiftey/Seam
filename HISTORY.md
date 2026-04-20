---BEGIN-ENTRY-#001---
id: 001
date: 2026-04-15T00:00:00Z
agent: claude-sonnet-4-6
status: done
topics: verify, retrieval, rank, vector, chroma, command
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 59
---
Retrieval and CLI work

- built and validated an experimental retrieval orchestrator
- added SQL + vector retrieval legs
- added result merging and ranking
- added context/RAG pack generation
- added optional Chroma semantic backend support
- cleaned up user-facing CLI terminology toward retrieval-oriented language
---END-ENTRY-#001---

---BEGIN-ENTRY-#002---
id: 002
date: 2026-04-15T00:01:00Z
agent: claude-sonnet-4-6
status: done
topics: retrieval, naming, alias
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 40
---
Retrieval naming cleanup

- moved the canonical experimental package to `experimental.retrieval_orchestrator`
- preserved `experimental.hybrid_orchestrator` as a compatibility import layer
- renamed canonical class/result types to retrieval-oriented names while keeping legacy aliases
---END-ENTRY-#002---

---BEGIN-ENTRY-#003---
id: 003
date: 2026-04-15T00:02:00Z
agent: claude-sonnet-4-6
status: done
topics: compile, search, dashboard, command, plan
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 80
---
Runtime-connected dashboard work

- added a real `dashboard` CLI command backed by the live SEAM runtime
- connected dashboard actions to compile, search, plan, retrieve, context, index, trace, and stats operations
- added scripted dashboard execution so the terminal surface can be smoke-tested automatically
- verified that a bad dashboard command path stays contained in the UI instead of crashing the process
---END-ENTRY-#003---

---BEGIN-ENTRY-#004---
id: 004
date: 2026-04-15T00:03:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, retrieval, lexical
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 91
---
Structured retrieval upgrade

- moved the SQLite retrieval leg away from a weak in-memory scan
- pushed explicit filters for `id`, `kind`, `ns`, `scope`, `predicate`, `subject`, and `object` into SQL
- added SQL-side lexical gating so broad filters do not pull in irrelevant records with zero text match
- added SQL-side ordering using structured score, lexical score, and record freshness/confidence
- added table indexes to support the stronger structured path
---END-ENTRY-#004---

---BEGIN-ENTRY-#005---
id: 005
date: 2026-04-15T00:04:00Z
agent: claude-sonnet-4-6
status: done
topics: retrieval, rank, dashboard, command
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 91
---
Richer context output

- added reusable context view formatting for `pack`, `prompt`, `evidence`, `summary`, and `records`
- kept pack generation as the canonical retrieval/context path while exposing richer operator-facing views on top
- extended the RAG result shape to include ranked candidates and exact record payloads so downstream renderers do not have to reconstruct retrieval state
- wired the new context views into both the CLI and the runtime-connected dashboard
---END-ENTRY-#005---

---BEGIN-ENTRY-#006---
id: 006
date: 2026-04-15T00:05:00Z
agent: claude-sonnet-4-6
status: done
topics: mirl, retrieval, compress, lx1, roundtrip, codec
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 106
---
Lossless machine-language benchmark

- added a dedicated `SEAM-LX/1` lossless machine-text format separate from MIRL compilation
- implemented reversible document compression using standard-library codecs with automatic best-codec selection
- added exact decompression with SHA-256 integrity checking so any mismatch fails loudly
- added benchmark reporting for token savings, byte savings, and intelligence-per-token gain using a deterministic prompt-token estimator
- added CLI commands for `lossless-compress`, `lossless-decompress`, and `lossless-benchmark`
- added a demo input file and regression coverage for exact roundtrips and high-savings benchmark passes
---END-ENTRY-#006---

---BEGIN-ENTRY-#007---
id: 007
date: 2026-04-16T00:00:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, verify, roundtrip, benchmark, installer, windows
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 119
---
Packaging, installer, and operator bootstrap

- added `pyproject.toml` so the repo can be installed editable
- exposed `seam` as the main console script and `seam-benchmark` as a focused benchmark shortcut
- added `seam demo lossless <source> <output>` and `--rebuild` for exact prove-it flows
- added tokenizer-aware benchmark reporting with `tiktoken` fallback behavior
- added `scripts/bootstrap_seam.ps1`, `scripts/enter_seam.ps1`, and `scripts/install_global_seam_command.ps1`
- added `seam doctor` as a lightweight install-health and smoke-test command
- added Windows and Linux installers with a dedicated runtime and persistent default database
- verified the Windows installer flow end to end
---END-ENTRY-#007---

---BEGIN-ENTRY-#008---
id: 008
date: 2026-04-16T00:01:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, verify, benchmark, bundle, fixture, command
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 98
---
Glassbox benchmark engine

- added `seam_runtime/benchmarks.py` as the six-family benchmark engine
- added benchmark bundle manifests, bundle hashes, case hashes, fixture hashes, and improvement-loop aggregation
- added benchmark persistence tables and read/write helpers in SQLite for machine artifacts, projections, runs, and cases
- added CLI flows for `benchmark run`, `benchmark show`, and `benchmark verify`
- added benchmark fixtures under `benchmarks/fixtures/`
- verified `benchmark verify` catches tampered bundles
- verified `benchmark show latest` works against persisted runs
---END-ENTRY-#008---

---BEGIN-ENTRY-#009---
id: 009
date: 2026-04-16T00:02:00Z
agent: claude-sonnet-4-6
status: done
topics: benchmark, naming, readme, multi-agent
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 75
---
Cross-agent continuity and benchmark blueprint

- refreshed `CLAUDE.md` so it matches the current repo instead of stale architecture assumptions
- added `GEMINI.md` and `ANTIGRAVITY.md` as assistant-specific resume guides
- added `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md` to hold the phase rollout and benchmark publication blueprint
- updated the repo-owned READMEs and durable memory files so terminology, benchmark policy, and next-step priorities are aligned
---END-ENTRY-#009---

---BEGIN-ENTRY-#010---
id: 010
date: 2026-04-17T00:00:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, vector, pgvector
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 49
---
PgVector Infrastructure Stabilization

- resolved Postgres 18+ volume mounting and credential issues via `docker-compose.yaml` with explicit `PGDATA` paths
- fixed DSN URL-encoding bugs for email-formatted database usernames
- confirmed stable local vector persistence with standard `psycopg` connection patterns
---END-ENTRY-#010---

---BEGIN-ENTRY-#011---
id: 011
date: 2026-04-17T00:01:00Z
agent: claude-sonnet-4-6
status: done
topics: verify, retrieval, vector, sbert, lx1, benchmark
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 84
---
Retrieval Projection Validation

- implemented a multi-track evaluation engine in `seam_runtime/evals.py` for Natural vs. Machine text comparisons
- added `SentenceTransformerModel` (SBERT) support to `seam_runtime/models.py` using `sentence-transformers`
- proved the "lossless retrieval" hypothesis: SEAM-LX/1 machine text preserves 100% retrieval recall when using neural embeddings, effectively closing the cross-domain gap without requiring a parallel natural-text index
- established the `benchmarks/runs/` JSON registry and [BENCHMARK_LOG.md](file:///c:/Users/iwana/OneDrive/Documents/Codex/benchmarks/BENCHMARK_LOG.md) for long-term tracking
---END-ENTRY-#011---

---BEGIN-ENTRY-#012---
id: 012
date: 2026-04-17T00:02:00Z
agent: claude-sonnet-4-6
status: done
topics: compile, persist, verify, search, vector, pgvector
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 78
---
PgVector Adapter Formal Verification

- added `FakePgVectorAdapter` to `test_seam.py` — subclasses `PgVectorAdapter`, overrides `_connect()` with an in-memory cursor and SQL log, no live Postgres required
- added `PgVectorAdapterTests` covering: schema DDL execution, record indexing, upsert dedup, scored search, DSN-based wiring in `SeamRuntime`, and full compile→persist→search round-trip
- all 54 tests green; `PgVectorAdapter` is now formally proven, not just manually confirmed
---END-ENTRY-#012---

---BEGIN-ENTRY-#013---
id: 013
date: 2026-04-17T00:03:00Z
agent: claude-sonnet-4-6
status: done
topics: vector, pgvector, doctor
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 78
---
SEAM_PGVECTOR_DSN Environment Variable Support

- `SeamRuntime` now picks up `SEAM_PGVECTOR_DSN` from the environment automatically — no explicit `pgvector_dsn` argument required
- `seam doctor` now checks `SEAM_PGVECTOR_DSN`, attempts a live connection, and reports reachability in its health output
- `seam doctor` dependency table extended to include `psycopg` and `sentence_transformers`
- env-var pickup covered by a new test (`test_runtime_picks_up_pgvector_dsn_from_env`); 55 tests green
---END-ENTRY-#013---

---BEGIN-ENTRY-#014---
id: 014
date: 2026-04-17T00:04:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, vector, pgvector, installer, linux, doctor
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 96
---
Linux Installer Validation (test-level)

- added `InstallerLinuxTests` covering: posix shim structure (shebang, SEAM_EXE, DB export, exec line, error guard), `path_in_environment` match/no-match, shell profile injection with temp home dir, dedup guard when marker already present, and `install_seam_linux.sh` script content
- updated doctor tests to assert new `PgVector:` line in pretty output and `pgvector`/`psycopg`/`sentence_transformers` keys in JSON output
- 62 tests green; Linux installer code paths are now fully exercised without requiring a real Linux machine
---END-ENTRY-#014---

---BEGIN-ENTRY-#015---
id: 015
date: 2026-04-17T00:05:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, vector, pgvector, bundle, dashboard, installer
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 118
---
Linux Installer Real-Machine Validation (WSL2 Ubuntu)

- fixed CRLF line endings in `install_seam_linux.sh` — `dash` rejected `set -eu` with CRLF terminators; added `.gitattributes` to enforce `*.sh eol=lf` permanently
- added `python3.12-venv` as a documented prerequisite (not bundled on Debian/Ubuntu by default)
- confirmed full install flow on Ubuntu WSL2 (Python 3.12.3): `seam --help` shows all commands, `seam dashboard` launches with persistent DB at `~/.local/share/seam/state/seam.db`, runtime log and all panels render correctly
- updated `installers/README.md` with Linux prereqs, venv guidance, optional extras install commands, dashboard launch, and full PgVector/Docker Compose setup section
---END-ENTRY-#015---

---BEGIN-ENTRY-#016---
id: 016
date: 2026-04-17T00:06:00Z
agent: claude-sonnet-4-6
status: done
topics: compile, mirl, persist, verify, search, vector
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 58
---
Core runtime: compile → verify → persist → search → pack

Set and executed across sessions 1–10.
- `compile-nl` and `compile-dsl` produce MIRL
- verification, SQLite persistence, vector indexing all working
- search, trace, pack, reconcile, transpile, and symbol export all working
Finished: 2026-04-17

---
---END-ENTRY-#016---

---BEGIN-ENTRY-#017---
id: 017
date: 2026-04-17T00:07:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, retrieval, rank, vector, chroma, plan
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 61
---
Retrieval and context pipeline

Set: early project planning.
- retrieval planning, structured + vector retrieval legs
- merged ranking, context/RAG pack generation
- `context` views: pack, prompt, evidence, summary, exact-record
- SQLite leg with SQL-side filtering and ranking
- Chroma as optional semantic backend
Finished: 2026-04-17

---
---END-ENTRY-#017---

---BEGIN-ENTRY-#018---
id: 018
date: 2026-04-17T00:08:00Z
agent: claude-sonnet-4-6
status: done
topics: verify, search, compress, lx1, codec, command
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 46
---
SEAM-LX/1 lossless compression

Set: step 8 planning.
- exact machine-text envelope with SHA-256 integrity verification
- lossless loop searches reversible transforms/codecs
- fluctuation/regression logging for debugging
- `seam demo lossless` one-command flow verified
Finished: 2026-04-17

---
---END-ENTRY-#018---

---BEGIN-ENTRY-#019---
id: 019
date: 2026-04-17T00:09:00Z
agent: claude-sonnet-4-6
status: done
topics: vector, pgvector, doctor, status, session
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 66
---
PgVector backend — formal testing and env-var support

Set: 2026-04-17 session.
- `FakePgVectorAdapter` test pattern for offline testing
- 6 PgVector adapter tests added to test suite
- `SEAM_PGVECTOR_DSN` env var pickup in `runtime.py`
- `seam doctor` now reports PgVector status + psycopg/sentence_transformers deps
- 62 tests green
Finished: 2026-04-17

---
---END-ENTRY-#019---

---BEGIN-ENTRY-#020---
id: 020
date: 2026-04-17T00:10:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, verify, benchmark, dashboard, installer, windows
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 48
---
Windows installer — end-to-end verification

Set: early project planning.
- `seam` and `seam-benchmark` packaged console commands
- `seam doctor` smoke test
- Windows installer verified end to end: command launch, persistence, lossless demo, dashboard
Finished: 2026-04-17

---
---END-ENTRY-#020---

---BEGIN-ENTRY-#021---
id: 021
date: 2026-04-17T00:11:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, verify, dashboard, installer, linux, wsl2
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 71
---
Linux installer — end-to-end verification

Set: 2026-04-17 session.
- Fixed CRLF line endings in `install_seam_linux.sh` (dash rejected `set -eu` with CRLF)
- Added `.gitattributes` to enforce `*.sh eol=lf` permanently
- Documented `python3.12-venv` as a prerequisite
- Confirmed full install on Ubuntu WSL2 (Python 3.12.3): `seam --help`, `seam dashboard`, persistent DB, all panels
Finished: 2026-04-17

---
---END-ENTRY-#021---

---BEGIN-ENTRY-#022---
id: 022
date: 2026-04-18T00:00:00Z
agent: claude-sonnet-4-6
status: done
topics: vector, sbert, pgvector, pyproject, extras
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 49
---
Optional Extras in pyproject.toml

- added `[project.optional-dependencies]` with `pgvector`, `sbert`, and `all-extras` groups
- `pip install seam-runtime[pgvector]` installs `psycopg[binary]>=3.0`
- `pip install seam-runtime[sbert]` installs `sentence-transformers>=2.0`
- base install remains lean; no heavy ML dependencies pulled in by default
---END-ENTRY-#022---

---BEGIN-ENTRY-#023---
id: 023
date: 2026-04-18T00:01:00Z
agent: claude-sonnet-4-6
status: done
topics: persist, retrieval, vector, sbert, pgvector, benchmark
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 118
---
Dashboard Review Pass (step 15)

- replaced misleading `Retrieval Backend` / `Vector Store Path` rows with `Vector Adapter` (shows actual adapter name: `sqlite-vector` or `pgvector`) and `PgVector DSN` (configured/not set)
- fixed execution mode: `local (neural)` for SBERT, not `cloud`
- commands panel redesigned as two-column table (command | args) — no more truncated tokenizer strings
- header subtitle split into two clean lines, tab buttons now have visible background highlight
- removed broken relative `benchmark tools/lossless_demo_input.txt` path from welcome text
- added `import os` to `dashboard.py`; 62 tests still green
---END-ENTRY-#023---

---BEGIN-ENTRY-#024---
id: 024
date: 2026-04-18T00:02:00Z
agent: claude-sonnet-4-6
status: done
topics: verify, benchmark, dashboard, command, naming, ledger
commits: none
refs: REPO_LEDGER.md#milestone-log
supersedes: none
tokens: 59
---
Roadmap & SOP Blueprint

- created `ROADMAP.md` as the full multi-track improvement plan with SOP approach for each track
- tracks: Dashboard & UI, Command Terminology, Benchmark Hardening, Model Skills & Automation, Architecture & Scalability
- ledger handoff block added below for next Claude session

---
---END-ENTRY-#024---

---BEGIN-ENTRY-#025---
id: 025
date: 2026-04-18T00:03:00Z
agent: claude-sonnet-4-6
status: done
topics: ledger, session, handoff
commits: cbc6aa4
refs: PLAN_LOG.md
supersedes: none
tokens: 58
---
Comprehensive ledger update + next-session handoff block

Set: 2026-04-18 session.
- Updated `REPO_LEDGER.md` with all session milestones
- Added handoff block at end of ledger for next Claude session
- Covers: last commits, stable features, next priorities, key files, rules
Finished: 2026-04-18
Commit: `cbc6aa4`

---
---END-ENTRY-#025---

---BEGIN-ENTRY-#026---
id: 026
date: 2026-04-18T00:04:00Z
agent: claude-sonnet-4-6
status: done
topics: compile, verify, vector, pgvector, compress, benchmark
commits: cbc6aa4
refs: PLAN_LOG.md
supersedes: none
tokens: 114
---
ROADMAP.md — multi-track improvement plan with SOP

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
---END-ENTRY-#026---

---BEGIN-ENTRY-#027---
id: 027
date: 2026-04-18T00:05:00Z
agent: claude-sonnet-4-6
status: done
topics: plan, history, session
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 53
---
PLAN_LOG.md — append-only plan history file

Set: 2026-04-18 session, from user request to keep a permanent record of all plans.
- Seeded with all plans from project start through 2026-04-18
- Append-only: never delete, never edit existing entries
Finished: 2026-04-18

---
---END-ENTRY-#027---

---BEGIN-ENTRY-#028---
id: 028
date: 2026-04-18T00:06:00Z
agent: claude-sonnet-4-6
status: planned
topics: compile, mirl, dashboard, animation, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 49
---
Dashboard animations — NL→MIRL compilation animation

Set: 2026-04-18. See `ROADMAP.md` Track A1.
- Rich `Live` streaming of record creation during `compile`
- Typewriter-style pop for each ENT/CLM/REL/ACT record
- Must not break `--snapshot` mode
Status: not started

---
---END-ENTRY-#028---

---BEGIN-ENTRY-#029---
id: 029
date: 2026-04-18T00:07:00Z
agent: claude-sonnet-4-6
status: planned
topics: benchmark, dashboard, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 48
---
Dashboard — benchmark progress bar & live metrics

Set: 2026-04-18. See `ROADMAP.md` Track A2.
- Rich `Progress` per benchmark family during `benchmark run`
- Live recall@k, token savings, pass/fail as each case completes
Status: not started

---
---END-ENTRY-#029---

---BEGIN-ENTRY-#030---
id: 030
date: 2026-04-18T00:08:00Z
agent: claude-sonnet-4-6
status: planned
topics: persist, benchmark, dashboard, graph, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 44
---
Dashboard — ASCII sparkline benchmark history graphs

Set: 2026-04-18. See `ROADMAP.md` Track A3.
- Query last 10 benchmark runs from SQLite
- Render per-family recall@k and token savings as sparklines
Status: not started

---
---END-ENTRY-#030---

---BEGIN-ENTRY-#031---
id: 031
date: 2026-04-18T00:09:00Z
agent: claude-sonnet-4-6
status: planned
topics: compile, search, dashboard, chat, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 61
---
Dashboard — Chat tab with Claude model

Set: 2026-04-18. See `ROADMAP.md` Track A5.
- New `chat` tab: user types query → SEAM retrieves context → Claude responds
- Claude can invoke SEAM tools: compile, search, context, stats
- Requires `anthropic` SDK optional extra
Status: not started

---
---END-ENTRY-#031---

---BEGIN-ENTRY-#032---
id: 032
date: 2026-04-18T00:10:00Z
agent: claude-sonnet-4-6
status: planned
topics: persist, benchmark, dashboard, animation, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 37
---
Dashboard — presentation mode (`--present`)

Set: 2026-04-18. See `ROADMAP.md` Track A6.
- Full-screen benchmark display with animated score bars
- Auto-refresh from latest persisted run
Status: not started

---
---END-ENTRY-#032---

---BEGIN-ENTRY-#033---
id: 033
date: 2026-04-18T00:11:00Z
agent: claude-sonnet-4-6
status: planned
topics: compile, search, compress, command, naming, alias
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 57
---
Command terminology audit & thematic naming

Set: 2026-04-18. See `ROADMAP.md` Track B1.
- Proposed theme: SEAM as a knowledge operating system
- `compile-nl` → `remember`, `search` → `find`, `compress` → `compress`, etc.
- Keep all existing names as compatibility aliases
Status: not started

---
---END-ENTRY-#033---

---BEGIN-ENTRY-#034---
id: 034
date: 2026-04-18T00:12:00Z
agent: claude-sonnet-4-6
status: planned
topics: vector, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 31
---
Argument consistency pass

Set: 2026-04-18. See `ROADMAP.md` Track B2.
- Consolidate `--vector-backend` / `--semantic-backend` → `--backend`
- Standardize `--budget` everywhere
Status: not started

---
---END-ENTRY-#034---

---BEGIN-ENTRY-#035---
id: 035
date: 2026-04-18T00:13:00Z
agent: claude-sonnet-4-6
status: planned
topics: benchmark, installer, readme, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 41
---
README consolidation

Set: 2026-04-18. See `ROADMAP.md` Track B3.
- `installers/README.md` → operator entry point
- `benchmarks/README.md` → benchmark operator docs
- Root `README.md` → index linking all docs
Status: not started

---
---END-ENTRY-#035---

---BEGIN-ENTRY-#036---
id: 036
date: 2026-04-18T00:14:00Z
agent: claude-sonnet-4-6
status: planned
topics: persist, benchmark, holdout, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 40
---
Holdout benchmark suites

Set: 2026-04-18. See `ROADMAP.md` Track C1.
- Cases never used during development
- `--holdout` flag gates publish-only runs
- Separate `benchmark_holdout_runs` table in SQLite
Status: not started

---
---END-ENTRY-#036---

---BEGIN-ENTRY-#037---
id: 037
date: 2026-04-18T00:15:00Z
agent: claude-sonnet-4-6
status: planned
topics: verify, benchmark, diff, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 33
---
Benchmark diff tooling

Set: 2026-04-18. See `ROADMAP.md` Track C2.
- `seam benchmark diff <run-a.json> <run-b.json>`
- Per-case delta with green/red improvement/regression columns
Status: not started

---
---END-ENTRY-#037---

---BEGIN-ENTRY-#038---
id: 038
date: 2026-04-18T00:16:00Z
agent: claude-sonnet-4-6
status: planned
topics: retrieval, vector, benchmark, gold-standard, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 42
---
Gold standard benchmarks (BEIR / MTEB / MS-MARCO)

Set: 2026-04-18. See `ROADMAP.md` Track C3.
- BEIR: 18 diverse retrieval tasks
- MTEB: embedding quality evaluation
- Adapters in `benchmarks/external/`
Status: not started

---
---END-ENTRY-#038---

---BEGIN-ENTRY-#039---
id: 039
date: 2026-04-18T00:17:00Z
agent: claude-sonnet-4-6
status: planned
topics: mirl, benchmark, fixture, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 32
---
Adversarial testing suite

Set: 2026-04-18. See `ROADMAP.md` Track C4.
- Malformed MIRL, adversarial queries, Unicode edge cases, concurrent writes
- `benchmarks/fixtures/adversarial/`
Status: not started

---
---END-ENTRY-#039---

---BEGIN-ENTRY-#040---
id: 040
date: 2026-04-18T00:18:00Z
agent: claude-sonnet-4-6
status: planned
topics: verify, benchmark, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 35
---
Cross-machine reproducibility checks

Set: 2026-04-18. See `ROADMAP.md` Track C5.
- `reference_run.json` locked in repo
- `seam benchmark verify --reference` checks scores within tolerance
Status: not started

---
---END-ENTRY-#040---

---BEGIN-ENTRY-#041---
id: 041
date: 2026-04-18T00:19:00Z
agent: claude-sonnet-4-6
status: planned
topics: compile, search, compress, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 42
---
SEAM as Claude tool set

Set: 2026-04-18. See `ROADMAP.md` Track D1.
- Define SEAM ops as Anthropic tool_use functions
- `seam_compile`, `seam_search`, `seam_context`, `seam_compress`, `seam_stats`
- `seam_runtime/tools.py` with `SeamToolExecutor`
Status: not started

---
---END-ENTRY-#041---

---BEGIN-ENTRY-#042---
id: 042
date: 2026-04-18T00:20:00Z
agent: claude-sonnet-4-6
status: planned
topics: compile, persist, compress, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 41
---
Auto-compression pipeline (`seam watch`)

Set: 2026-04-18. See `ROADMAP.md` Track D2.
- Watch a directory → compress new files → compile-nl → persist → index
- `watchdog` optional extra
Status: not started

---
---END-ENTRY-#042---

---BEGIN-ENTRY-#043---
id: 043
date: 2026-04-18T00:21:00Z
agent: claude-sonnet-4-6
status: planned
topics: compile, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 36
---
Batch compile (`seam batch-compile <glob>`)

Set: 2026-04-18. See `ROADMAP.md` Track D3.
- Parallel file processing via `ThreadPoolExecutor`
- Rich progress bar + summary JSON
Status: not started

---
---END-ENTRY-#043---

---BEGIN-ENTRY-#044---
id: 044
date: 2026-04-18T00:22:00Z
agent: claude-sonnet-4-6
status: planned
topics: persist, vector, pgvector, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 36
---
PgVector migration helper

Set: 2026-04-18. See `ROADMAP.md` Track E1.
- `seam migrate-vectors --to pgvector`
- Reads SQLite vector_index, writes to PgVector, verifies row counts
Status: not started

---
---END-ENTRY-#044---

---BEGIN-ENTRY-#045---
id: 045
date: 2026-04-18T00:23:00Z
agent: claude-sonnet-4-6
status: planned
topics: command, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 35
---
Multi-tenant namespacing

Set: 2026-04-18. See `ROADMAP.md` Track E2.
- `tenant_id` column on `ir_records` and related tables
- `--tenant` flag on all CLI commands
Status: not started

---
---END-ENTRY-#045---

---BEGIN-ENTRY-#046---
id: 046
date: 2026-04-18T00:24:00Z
agent: claude-sonnet-4-6
status: planned
topics: compile, search, roadmap, status
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 45
---
REST API surface (`seam serve`)

Set: 2026-04-18. See `ROADMAP.md` Track E3.
- FastAPI + uvicorn optional extra
- Endpoints: `/compile`, `/search`, `/context`, `/stats`, `/health`
- Bearer token auth via env var
Status: not started

---
---END-ENTRY-#046---

---BEGIN-ENTRY-#047---
id: 047
date: 2026-04-18T00:25:00Z
agent: claude-sonnet-4-6
status: planned
topics: compile, persist, retrieval, search, benchmark, dashboard
commits: none
refs: PLAN_LOG.md
supersedes: none
tokens: 529
---
True interactive TUI dashboard — live panels, in-place input, scrollable boxes

Set: 2026-04-18. User request: make the dashboard a proper live terminal UI.

**What:**
- `seam-dash` (or `seam dashboard`) launches a full interactive TUI — one persistent session, never re-renders the whole screen on input
- Input is handled in-place at the bottom of the screen; results update the relevant panel without flashing or reprinting
- Panels that hold constantly-updating data (records, search results, benchmark stats, logs) are independently scrollable within their own bordered boxes — user can scroll one panel while the others keep refreshing
- The dashboard becomes its own first-class CLI tool (`seam-dash` console entrypoint in `pyproject.toml`)

**How (proposed stack):**
- Migrate from `Rich.Live` (which re-renders the full layout) to **Textual** — a proper TUI framework built on Rich that supports:
  - widgets with independent scroll buffers
  - reactive data bindings (panels auto-update when data changes)
  - keyboard-driven input without re-rendering the whole screen
  - proper focus management between panels
- Alternatively: keep Rich but use `Rich.Live` + `Rich.Layout` with a custom input loop that patches only the changed panel regions (harder, less clean)
- Textual is the recommended path — it is designed exactly for this and outputs a polished app

**Panels that need independent scroll:**
- Memory Records panel (grows with every compile)
- Search / Retrieval Results panel
- Benchmark Results panel
- Runtime Log / Event stream
- Chat history (when Chat tab is added — Track A5)

**Entrypoint:**
- Add `seam-dash = "seam_runtime.dashboard:main"` to `[project.scripts]` in `pyproject.toml`
- `seam-dash` launches the TUI directly; `seam dashboard` remains as an alias

**SOP:**
1. Install `textual` as an optional extra (`seam-runtime[dash]`) or promote to a base dependency if the dashboard is a primary interface
2. Port existing dashboard panels to Textual widgets one at a time — keep the Rich snapshot fallback working throughout
3. Implement scrollable `DataTable` or `ListView` widgets for records, results, logs
4. Wire input bar at the bottom as a Textual `Input` widget — on submit, runs the existing `execute()` logic and updates the relevant panel reactively
5. Add `seam-dash` console entrypoint to `pyproject.toml`
6. Test: `--snapshot` mode must still work (Textual supports headless export)
7. Gate: all 62 existing tests must pass; add at least 3 TUI widget tests

**Gate:** Dashboard must not flash or re-render the whole screen on any user input. Each panel scrolls independently. Works on Windows terminal and Linux/WSL2.
Status: not started

---
---END-ENTRY-#047---

---BEGIN-ENTRY-#048---
id: 048
date: 2026-04-20T04:12:38Z
agent: codex-gpt-5
status: done
topics: history, snapshot, multi-agent, protocol, integrity, ledger
commits: none
refs: PROJECT_STATUS.md,REPO_LEDGER.md,HISTORY_INDEX.md,AGENTS.md
supersedes: none
tokens: 97
---
Completed Phase 1 context-memory migration in repo root.

- Restored canonical history tooling in tools/history and added seed_from_existing migration script.
- Seeded HISTORY.md and rebuilt compact HISTORY_INDEX.md with hash verification.
- Collapsed duplicated continuity docs into pointer-card protocol: REPO_LEDGER.md, PROJECT_STATUS.md, CLAUDE.md, GEMINI.md, ANTIGRAVITY.md.
- Removed PLAN_LOG.md after migration to canonical history.
- Updated ROADMAP.md to remove duplicated state snapshot and point to HISTORY entries.
- Reduced required startup read budget to under 2,000 estimated tokens.
---END-ENTRY-#048---

---BEGIN-ENTRY-#049---
id: 049
date: 2026-04-20T08:19:21Z
agent: codex-gpt-5
status: done
topics: dashboard, textual, command, pyproject, history, snapshot
commits: none
refs: seam_runtime/dashboard.py,pyproject.toml,test_seam.py
supersedes: none
tokens: 83
---
A0 Textual migration baseline started.
- Added Textual interactive dashboard path with persistent input and independently scrollable panels.
- Preserved Rich snapshot/script rendering path for `seam dashboard --snapshot` and scripted `--run` flows.
- Added `seam-dash` entrypoint and `dash` optional dependency in pyproject.
- Added Textual dashboard tests (widget mount + command routing), skipped when Textual is not installed.
Refs: see HISTORY#047 for roadmap pointer.
---END-ENTRY-#049---

---BEGIN-ENTRY-#050---
id: 050
date: 2026-04-20T16:59:32Z
agent: codex-gpt-5
status: done
topics: dashboard, textual, command, roadmap, history, snapshot
commits: none
refs: seam_runtime/dashboard.py,test_seam.py,ROADMAP.md
supersedes: none
tokens: 92
---
Continued A0 Textual migration with tab/state synchronization.
- Added explicit tab bar rendering and refresh logic tied to `tab runtime|benchmark`.
- Side panel now syncs with active tab: runtime events in Runtime mode, benchmark search-log entries in Benchmark mode.
- Added Textual test coverage for tab-switch side-panel behavior.
- Added Track F roadmap items for operator setup docs, documented error playbooks, and how-to runbooks.
Refs: see HISTORY#049 for prior A0 baseline.
---END-ENTRY-#050---

---BEGIN-ENTRY-#051---
id: 051
date: 2026-04-20T19:07:05Z
agent: codex-gpt-5
status: done
topics: dashboard, textual, pyproject, readme, command, history, snapshot
commits: none
refs: pyproject.toml,requirements.txt,seam_runtime/dashboard.py,README.md,installers/README.md,docs/setup.md,docs/errors.md,docs/howto/README.md,test_seam.py
supersedes: none
tokens: 114
---
Dependency and docs hardening for Textual testability and operator setup.
- Installed `textual` and fixed Textual dashboard widget implementation so Textual tests execute and pass in an environment with deps installed.
- Updated dependency constraints to keep `rich` compatible with Textual (`rich>=14.2,<16`) in pyproject and requirements.
- Added copy/paste setup and troubleshooting docs: docs/setup.md, docs/errors.md, docs/howto/README.md.
- Linked setup/troubleshooting docs from README and installers/README; documented `dash` extra install path.
- Verified dashboard/Textual test suite and doctor pass with installed dependencies.
Refs: see HISTORY#050 for prior dashboard tab-state migration.
---END-ENTRY-#051---

---BEGIN-ENTRY-#052---
id: 052
date: 2026-04-20T20:22:36Z
agent: codex-gpt-5
status: done
topics: dashboard, textual, chat, animation, command, history, snapshot
commits: none
refs: seam_runtime/dashboard.py,test_seam.py
supersedes: none
tokens: 105
---
Expanded Textual dashboard toward full CLI assistant surface.
- Added SEAM logo header, chat panel, command-history panel, MIRL compression animation panel, and live token/db metric bars.
- Added input-mode shortcuts and routing: /model, /cmd, /hybrid, /help, /clear, plus ! force-command and ? force-chat.
- Added model-chat client integration path (OpenAI-compatible via SEAM_CHAT_API_KEY/OPENAI_API_KEY).
- Updated Textual tests to validate ! command path and shortcut mode switching.
- Verified dashboard test suite passes with dependencies installed.
Refs: see HISTORY#051 for dependency/docs hardening baseline.
---END-ENTRY-#052---

---BEGIN-ENTRY-#053---
id: 053
date: 2026-04-20T20:36:17Z
agent: codex-gpt-5
status: done
topics: dashboard, textual, chat, command, history, snapshot
commits: none
refs: seam_runtime/dashboard.py,test_seam.py
supersedes: none
tokens: 115
---
Dashboard polish follow-up delivered for CLI-like Textual experience.
- Tightened Textual layout density (header/metrics/tab sizing, larger results row, reduced panel margins) for higher information throughput.
- Added chat transcript export shortcuts: `/savechat [path]` and `/export-chat [path]`, with default output to `.seam/chat_transcripts/chat-<timestamp>.jsonl`.
- Added command-history status badges and timing annotations (`[RUN]`, `[OK]`, `[ERR]`, with ms/s elapsed formatting).
- Added defensive empty-chat handling and header chat model/status indicator.
- Added Textual tests for transcript export and command-history status/timing; verified focused dashboard/Textual suite passes.
Refs: see HISTORY#052 for prior dashboard expansion baseline.
---END-ENTRY-#053---

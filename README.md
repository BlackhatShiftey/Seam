# SEAM

SEAM is an on-device memory runtime for AI agents.

Its core use is machine-first: you hand an agent this repo with a prompt like "configure SEAM for persistent memory, reduce token usage, compress stored data into machine language, and use SEAM as the agent's memory substrate," and SEAM becomes the local system the agent uses to persist, retrieve, trace, benchmark, and compress its own working data.

Its main job is not to be a human-facing app. Its main job is to give an agent a durable memory/runtime substrate it can compile into, retrieve from, trace, verify, compress, and reason over locally.

The CLI and terminal dashboard are the glassbox around that system:

- inspect what the runtime stored
- run tests and six-family benchmarks
- investigate retrieval behavior
- trace provenance and exact records
- watch the system do AI work without hiding the internals

If you are looking for the product surface, think agent first and machine first. If you are looking for the operator surface, think CLI and dashboard.

## Why This Repo Exists

SEAM is split into a few distinct layers:

- `SEAM`: the runtime, CLI, dashboard, adapters, benchmark engine, and Python surface
- `MIRL`: the canonical memory IR inside SEAM
- `PACK`: derived prompt-time context views
- `SEAM-LX/1`: an exact lossless machine-text envelope for document compression demos and token-efficiency benchmarks

Design stance:

- SQLite is the canonical source of truth
- vectors and Chroma are derived retrieval layers, not canonical storage
- the benchmark engine is a glassbox proof surface, not marketing-only output
- the dashboard is a glassbox operator surface, not the primary interface
- the highest-value use case is an AI agent running on a device with SEAM embedded underneath it
- stored and retrieved data should trend toward machine-efficient representations when SEAM can do so without violating exactness or canonical storage guarantees

## Core Use

The central SEAM workflow is:

1. hand an agent this repo and a task prompt
2. let the agent configure SEAM as its persistent local memory system
3. let the agent store canonical records in SQLite
4. let the agent derive compact machine-facing views for retrieval, prompting, benchmarking, and exact document compression
5. let the agent search its own database using those reduced-token views while preserving traceability back to canonical records

In other words, SEAM is meant to help an agent use fewer tokens against its own memory without losing the ability to recover exact source state.

## Current Capabilities

- compile natural language into MIRL
- compile a narrow DSL into MIRL
- verify MIRL schema and exact-pack reversibility
- persist MIRL, provenance, raw evidence, packs, machine artifacts, projections, and benchmark reports into SQLite
- search, trace, pack, reconcile, transpile, and export symbols
- run hybrid retrieval over SQL, lexical, graph, temporal, and optional vector signals
- render `context` output as `pack`, `prompt`, `evidence`, `summary`, or exact `records`
- run a six-family benchmark engine covering `lossless`, `retrieval`, `embedding`, `long_context`, `persistence`, and `agent_tasks`
- record bundle hashes, case hashes, fixture hashes, improvement-loop actions, and persisted benchmark history
- run a lossless `SEAM-LX/1` benchmark that only passes on exact reconstruction
- show runtime state and benchmark loops in a terminal dashboard

## Bare Checkout Setup

SEAM now treats `rich`, `chromadb`, and `tiktoken` as required base dependencies.
If you want the installed terminal commands so you can type `seam` directly, use the installer path below.

Recommended baseline:

```powershell
git clone <your-fork-or-repo-url>
cd Seam
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the core test suite:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Notes:

- `seam doctor` reports `FAIL` if required deps (`rich`, `chromadb`, `tiktoken`) are missing
- optional extras are only for additional backends/features beyond base runtime

## Installer Flow

If you want the "download installer, run installer, type `seam`" path, use the installer entrypoint for your platform.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\install_seam_windows.ps1
```

Linux:

```bash
sh ./installers/install_seam_linux.sh
```

What the installer does:

- creates a dedicated SEAM runtime under your home directory instead of relying on a repo-local venv
- installs SEAM into that dedicated runtime
- creates global `seam` and `seam-benchmark` shims
- configures a persistent default database in the SEAM install state directory
- updates a user PATH location or shell profile as needed
- runs `seam doctor`

After the installer finishes, open a new terminal and type:

```text
seam doctor
seam --help
```

Default persistence paths:

- Windows: `%LOCALAPPDATA%\SEAM\state\seam.db`
- Linux: `~/.local/share/seam/state/seam.db`

## Repo-Local Development Install

If you want `seam` and `seam-benchmark` as real terminal commands just for the current checkout:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

Fastest repo-local development path:

```powershell
.\scripts\bootstrap_seam.ps1
```

That script will:

- create `.venv` if needed
- install SEAM in editable mode
- install global `seam` and `seam-benchmark` shims into a user PATH location
- verify `seam.exe` and `seam-benchmark.exe`
- run `seam doctor`

To drop into a shell where you can type `seam` directly:

```powershell
. .\scripts\enter_seam.ps1
```

Optional extras:

- `pgvector` for PostgreSQL pgvector backend
- `sbert` for sentence-transformer embeddings
- `all-extras` for both

## Quick Start

### 1. Compile and Persist Memory

If you installed SEAM through the platform installer, `seam` already points at the persistent default database in the SEAM state directory. You only need `--db` when you want to override that default for an experiment or test.

```powershell
seam compile-nl "We need durable memory for AI systems." --persist
seam index
seam search "durable memory" --budget 5
```

### 2. Retrieve Agent Context

```powershell
seam retrieve "translator natural language" --budget 5 --trace
seam context "translator natural language" --view prompt
seam context "translator natural language" --view evidence --format json
seam context "translator natural language" --view records
```

### 3. Launch the Glassbox Dashboard

Requires `rich`:

```powershell
seam dashboard
```

Useful non-interactive snapshots:

```powershell
seam dashboard --snapshot --no-clear
seam dashboard --run "tab benchmark" --run "benchmark tools/lossless_demo_input.txt --min-savings 0.75" --run "decompress-last" --no-clear
```

## Benchmark Glassbox

SEAM now ships with a six-family benchmark engine that records raw per-case traces, persisted run history, bundle hashes, case hashes, fixture hashes, and improvement-loop actions.

Benchmark families:

- `lossless`
- `retrieval`
- `embedding`
- `long_context`
- `persistence`
- `agent_tasks`

Run the full suite and persist the result:

```powershell
seam benchmark run all --persist --output seam-benchmark-report.json
```

Inspect the latest persisted run:

```powershell
seam benchmark show latest
```

Verify that a saved bundle has not been tampered with:

```powershell
seam benchmark verify seam-benchmark-report.json
```

Run only the lossless family with an explicit tokenizer:

```powershell
seam benchmark run lossless --tokenizer cl100k_base --include-machine-text
```

The benchmark blueprint and contributor-facing methodology live here:

- `benchmarks/README.md`
- `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md`

## Lossless Machine-Language Demo

`SEAM-LX/1` is an exact machine-text envelope. It is not a summary and it is not allowed to drop information.

The workflow is:

1. feed SEAM a document
2. get back a compressed machine-text version plus compression stats
3. feed the machine text back in
4. rebuild the original document exactly

The benchmark only passes if the roundtrip is lossless and the compressed form meets the requested token-savings threshold.

```powershell
seam demo lossless C:\path\to\document.txt C:\path\to\document.seamlx --min-savings 0.75
seam demo lossless C:\path\to\document.seamlx C:\path\to\rebuilt.txt --rebuild
cmd /c fc /b C:\path\to\document.txt C:\path\to\rebuilt.txt
```

Focus on exactness first. If a document does not hit the savings target, the benchmark should fail rather than pretend the compression is good enough.

## Cross-Agent Continuity

The durable project memory lives in:

- `PROJECT_STATUS.md`
- `REPO_LEDGER.md`

Agent-specific continuity files now exist so other assistants can resume work quickly without inventing their own repo model:

- `CLAUDE.md`
- `GEMINI.md`
- `ANTIGRAVITY.md`

These are resume guides, not alternate sources of truth. The canonical project memory is still `PROJECT_STATUS.md` plus `REPO_LEDGER.md`.

## Agent Integration Use

If you are using SEAM the intended way, the main interface is not the dashboard. The main interface is the AI agent that runs on the device and uses SEAM underneath it.

A practical handoff prompt looks like:

```text
Configure SEAM for persistent memory, keep SQLite canonical, reduce token usage through machine-efficient derived views, benchmark every major change, and do not accept any lossy compression path.
```

That is the core of the project: not a mystery box UI, but a machine-first local runtime that gives an agent durable memory, exact recovery, and measurable token-efficiency gains.

# SEAM

SEAM is an on-device memory runtime for AI agents.

Its core use is machine-first: you hand an agent this repo with a prompt like "configure SEAM for persistent memory, reduce token usage, compress stored data into machine language, and use SEAM as the agent's memory substrate," and SEAM becomes the local system the agent uses to persist, retrieve, trace, and compress its own working data.

Its main job is not to be a human-facing app. Its main job is to give an agent a durable memory/runtime substrate it can compile into, retrieve from, trace, verify, compress, and reason over locally.

The CLI and terminal dashboard are the glassbox around that system:

- inspect what the runtime stored
- run tests and benchmarks
- investigate retrieval behavior
- trace provenance and exact records
- watch the system do AI work without hiding the internals

If you are looking for the "product surface," think agent first and machine first. If you are looking for the operator surface, think CLI and dashboard.

## Why This Repo Exists

SEAM is split into a few distinct layers:

- `SEAM`: the runtime, CLI, dashboard, adapters, and Python surface
- `MIRL`: the canonical memory IR inside SEAM
- `PACK`: derived prompt-time context views
- `SEAM-LX/1`: an exact lossless machine-text envelope for document compression demos and token-efficiency benchmarks

Design stance:

- SQLite is the canonical source of truth
- vectors and Chroma are derived retrieval layers, not canonical storage
- the dashboard is a glassbox operator surface, not the primary interface
- the highest-value use case is an AI agent running on a device with SEAM embedded underneath it
- stored and retrieved data should trend toward machine-efficient representations when SEAM can do so without violating exactness or canonical storage guarantees

## Core Use

The central SEAM workflow is:

1. hand an agent this repo and a task prompt
2. let the agent configure SEAM as its persistent local memory system
3. let the agent store canonical records in SQLite
4. let the agent derive compact machine-facing views for retrieval, prompting, and exact document compression
5. let the agent search its own database using those reduced-token views while preserving traceability back to canonical records

In other words, SEAM is meant to help an agent use fewer tokens against its own memory without losing the ability to recover exact source state.

## Current Capabilities

- compile natural language into MIRL
- compile a narrow DSL into MIRL
- verify MIRL schema and exact-pack reversibility
- persist MIRL, provenance, raw evidence, and packs into SQLite
- search, trace, pack, reconcile, transpile, and export symbols
- run hybrid retrieval over SQL, lexical, graph, temporal, and optional vector signals
- render `context` output as `pack`, `prompt`, `evidence`, `summary`, or exact `records`
- run a lossless `SEAM-LX/1` benchmark that only passes on exact reconstruction
- show runtime state and benchmark loops in a terminal dashboard

## Bare Checkout Setup

SEAM's core runtime, tests, and lossless benchmark work from a bare checkout with standard-library Python only. If you want the installed terminal commands so you can type `seam` directly, do the editable install path below.

Recommended baseline:

```powershell
git clone <your-fork-or-repo-url>
cd Seam
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Run the core test suite with no extra dependencies:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

Notes:

- if `rich` is not installed, dashboard-specific tests skip automatically
- the lossless codec and benchmark do not require `rich`, `chromadb`, or `tiktoken`

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

The installer path is the intended operator path. It is designed so a person or an agent can bootstrap SEAM once, then use `seam` as the machine-first local runtime command without thinking about a repo-local virtual environment.

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

That installs the packaged CLI plus:

- `rich` for the terminal dashboard
- `chromadb` for the optional Chroma vector backend
- `tiktoken` for tokenizer-backed benchmark counts

On Windows you can then run either:

```powershell
.\.venv\Scripts\seam.exe --help
.\.venv\Scripts\seam-benchmark.exe tools/lossless_demo_input.txt --min-savings 0.75
```

Or activate the venv first and use:

```powershell
seam --help
seam-benchmark tools/lossless_demo_input.txt --min-savings 0.75
```

Smoke-test the install:

```powershell
seam doctor
```

After `bootstrap_seam.ps1`, new PowerShell windows should also be able to run `seam` directly without activating the repo venv first. The repo-local helper is mainly for development; the installer flow above is the intended operator path.

## Optional Extras

If you want the optional runtime extras without installing the package entrypoints:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

That currently installs:

- `rich` for the terminal dashboard
- `chromadb` for the optional Chroma vector backend
- `tiktoken` for tokenizer-backed benchmark counts

If PowerShell blocks activation and you want an activated shell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

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

## Lossless Machine-Language Demo

`SEAM-LX/1` is an exact machine-text envelope. It is not a summary and it is not allowed to drop information.

The current demo path is verified for UTF-8 text documents.

The workflow is:

1. feed SEAM a document
2. get back a compressed machine-text version plus compression stats
3. feed the machine text back in
4. rebuild the original document exactly

The benchmark only passes if the roundtrip is lossless and the compressed form meets the requested token-savings threshold.

The simplest prove-it flow is now:

```powershell
seam demo lossless C:\path\to\document.txt C:\path\to\document.seamlx --min-savings 0.75
seam demo lossless C:\path\to\document.seamlx C:\path\to\rebuilt.txt --rebuild
cmd /c fc /b C:\path\to\document.txt C:\path\to\rebuilt.txt
```

Run the demo:

```powershell
seam demo lossless tools/lossless_demo_input.txt demo.seamlx --min-savings 0.75 --log-output benchmark-log.json --show-machine
seam demo lossless demo.seamlx rebuilt.txt --rebuild
cmd /c fc /b tools\lossless_demo_input.txt rebuilt.txt
```

What the benchmark does:

- tries the currently known reversible transforms and codecs
- keeps the best exact candidate
- logs every attempt
- flags compression fluctuations and regressions for debugging
- stops when no known candidate improves the current best result
- prefers tokenizer-backed counts when `tiktoken` is installed and falls back to `char4_approx` otherwise

The included demo input currently clears the `75%` token-savings bar while still reconstructing exactly.

## CLI Surface

The CLI is primarily for interacting with stored data, investigating the runtime, and running tests and benchmarks. It is intentionally useful as a tool, but it is not the main product surface.

### Memory and Compilation

- `ingest`: store raw text from a file or stdin
- `compile-nl`: compile natural language into MIRL
- `compile-dsl`: compile a SEAM DSL file into MIRL
- `verify`: validate MIRL from a text file
- `persist`: persist MIRL from a text file

### Retrieval and Context

- `search`: combined search over persisted MIRL
- `plan`: show a retrieval plan
- `retrieve`: run ranked retrieval
- `compare`: compare basic search with retrieval ranking
- `context`: build generation context with `--view pack|prompt|evidence|summary|records`
- `index`: sync persisted records into the active vector indexes

### Inspection and Debugging

- `dashboard`: launch the runtime-connected terminal dashboard
- `doctor`: check install health and run a lightweight compile/lossless smoke test
- `demo lossless`: one-command operator demo for compressing and rebuilding exact machine text
- `trace`: inspect provenance for an object id
- `pack`: build a pack from persisted record ids
- `decompile`: expand persisted record ids back to readable output
- `stats`: emit retrieval benchmark summary data

### Runtime Maintenance

- `reconcile`: reconcile claims and emit relation or state updates
- `transpile`: transpile MIRL workflows to Python stubs
- `reindex`: rebuild vector index entries
- `promote-symbols`: propose and persist machine-only symbols
- `export-symbols`: export the symbol nursery for audit and safety review

### Lossless Document Tools

- `lossless-compress` or `compress-doc`: encode a document into `SEAM-LX/1`
- `lossless-decompress` or `decompress-doc`: recover the exact original text
- `lossless-benchmark` or `benchmark-doc`: run the exact roundtrip benchmark and emit compression data
- `seam-benchmark`: packaged terminal shortcut for the lossless benchmark

## Dashboard Surface

The dashboard is for investigation, debugging, and understanding what SEAM is doing.

It supports:

- interactive runtime commands
- one-shot snapshots
- scripted `--run` command sequences
- a runtime tab
- a benchmark tab

Inside the dashboard you can do things like:

```text
tab benchmark
benchmark tools/lossless_demo_input.txt --min-savings 0.75
decompress-last
tab runtime
context translator natural language --view evidence
trace CLM:translator
```

## Python Surface For Agents

The intended high-value use case is an agent embedding SEAM directly and using it as a memory/compression substrate for its own work:

```python
from seam import SeamRuntime, lossless_benchmark

runtime = SeamRuntime("seam.db")
result = runtime.compile_nl("We need durable memory for AI systems.")
benchmark = lossless_benchmark("Exact reversible document payload")
```

The machine-first goal is not just "store notes in a database." The goal is for the agent to progressively use SEAM to:

- keep durable local memory
- reduce token usage during retrieval and context building
- compress exact documents into machine text when lossless recovery matters
- operate over compact derived representations while keeping canonical records recoverable

The CLI is there so humans can inspect and steer the system. The agent runtime is the real center of gravity.

## Chroma-Backed Retrieval

Chroma is optional and derived. SQLite remains canonical.

Example:

```powershell
.\.venv\Scripts\python.exe seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows." --persist
.\.venv\Scripts\python.exe seam.py --db seam.db index --vector-backend chroma --vector-path .seam_chroma
.\.venv\Scripts\python.exe seam.py --db seam.db context "translator natural language" --vector-backend chroma --vector-path .seam_chroma --view summary
```

## Important Docs

- [PROJECT_STATUS.md](PROJECT_STATUS.md)
- [REPO_LEDGER.md](REPO_LEDGER.md)
- [SEAM_SPEC_V0.1.md](SEAM_SPEC_V0.1.md)
- [docs/MIRL_V1.md](docs/MIRL_V1.md)
- [docs/RETRIEVAL_EVAL_V1.md](docs/RETRIEVAL_EVAL_V1.md)
- [docs/SOP_MODEL_INTEGRATION.md](docs/SOP_MODEL_INTEGRATION.md)
- [docs/SYMBOL_NURSERY.md](docs/SYMBOL_NURSERY.md)

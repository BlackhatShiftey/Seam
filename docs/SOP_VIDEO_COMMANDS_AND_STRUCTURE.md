# SOP: Video Script for SEAM Commands and Project Structure

This document is a narration-first SOP for explaining SEAM in a video.

Use it when you want to walk through:

- what SEAM is
- how the repo is organized
- what each major command is for
- what order to demo things in
- which files matter when you are explaining architecture

The goal is to keep the explanation clear, practical, and grounded in the actual repo.

## 1. Video goal

The goal of this video is to show that SEAM is not just a pile of scripts.
It is a structured memory runtime with a clear layout:

- the root gives you the entrypoints and operator commands
- `seam_runtime/` holds the actual system logic
- `docs/` explains the concepts and operating rules
- `scripts/` handles local environment bootstrapping

The best video arc is:

1. explain what SEAM is
2. show how the repo is laid out
3. show the local setup flow
4. show the main CLI commands
5. explain where each command routes in the code
6. close with what is canonical truth versus what is derived

## 2. Short on-camera summary

Suggested opening:

> SEAM is a memory-first compiler and runtime for AI systems. The core idea is that natural language or a narrow DSL gets compiled into MIRL, which is SEAM's canonical memory representation. From there, SEAM can verify that memory, store it, search it, pack it into context, and build compact machine-facing views without losing track of the original record structure.

Short version:

- `SEAM` is the runtime and CLI
- `MIRL` is the canonical memory IR
- `PACK` is the derived context view

## 3. Repo structure script

Suggested narration:

> At the repo root, I have the operator layer. This is where I start if I want to run SEAM, test SEAM, or set up the local environment. The root has the README, the main seam.py entrypoint, the test suite, the environment setup scripts, and the top-level docs.

### Root files to mention

- `README.md`
  - high-level overview
  - quick-start setup
  - storage blueprint

- `seam.py`
  - public entrypoint
  - the command I run from the terminal

- `test_seam.py`
  - main regression suite
  - the fastest confidence check after changes

- `requirements.txt`
  - Python dependencies

- `compose.yaml`
  - local pgvector/Postgres service definition

- `.env.example`
  - safe template for local DB configuration

### Runtime package to mention

Suggested narration:

> The real system logic lives in seam_runtime. That package is split by responsibility instead of being one giant file.

- `seam_runtime/cli.py`
  - CLI argument definitions and dispatch

- `seam_runtime/runtime.py`
  - the orchestration layer
  - this is where compile, verify, persist, retrieve, pack, and symbol flows get coordinated

- `seam_runtime/nl.py`
  - natural-language to MIRL compilation

- `seam_runtime/dsl.py`
  - DSL to MIRL compilation

- `seam_runtime/mirl.py`
  - MIRL data structures and serialization

- `seam_runtime/verify.py`
  - validation rules and reports

- `seam_runtime/storage.py`
  - SQLite persistence

- `seam_runtime/retrieval.py`
  - hybrid retrieval ranking

- `seam_runtime/vector.py`
  - vector utilities and shared text rendering

- `seam_runtime/vector_adapters.py`
  - SQLite vector adapter and pgvector adapter

- `seam_runtime/models.py`
  - embedding model abstraction

- `seam_runtime/pack.py`
  - pack generation and exact unpacking

- `seam_runtime/symbols.py`
  - symbol proposal and export

- `seam_runtime/reconcile.py`
  - conflicting or duplicate claim handling

- `seam_runtime/evals.py`
  - retrieval evaluation and benchmark logic

### Docs folder to mention

Suggested narration:

> The docs folder is where the conceptual contracts live. If I want to explain the system instead of just run it, this is the layer I point people to.

- `docs/PROJECT_MAP.md`
  - where code responsibilities live

- `docs/COMMANDS.md`
  - the practical command list

- `docs/MIRL_V1.md`
  - canonical IR explanation

- `docs/SOP_MODEL_INTEGRATION.md`
  - embeddings, vector layers, and model boundaries

- `docs/RETRIEVAL_EVAL_V1.md`
  - how retrieval quality is judged

- `docs/SYMBOL_NURSERY.md`
  - symbol governance and export expectations

## 4. Command categories

When explaining commands in a video, group them by purpose instead of reading them like a flat list.

### Setup commands

These commands are for getting the local environment ready.

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
notepad .env
.\scripts\setup-seam.ps1 -UserName "your-user" -DatabaseName "seam"
```

Suggested narration:

> This is the copy-paste setup path. I copy the safe env template, manually set my local database credentials in .env, and then run the setup script. That script installs Python dependencies, starts the local pgvector-enabled Postgres service, enables the vector extension, and exports the session DSN I need for pgvector-backed tests.

If you want to explain the lighter bootstrap path:

```powershell
. .\scripts\pgvector-up.ps1
```

Suggested narration:

> If my environment is already configured, I can skip the full setup pass and just bring up the local pgvector service in the current shell session.

### Sanity check commands

These commands prove the install is healthy.

```powershell
python seam.py --help
python -m unittest test_seam.py
```

Suggested narration:

> The first command proves the CLI loads. The second command is the real confidence check, because it verifies the actual runtime behavior instead of just showing that argparse works.

### Authoring and indexing commands

These commands create or enrich memory.

```powershell
python seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows." --persist
python seam.py --db seam.db promote-symbols --min-frequency 1
python seam.py --db seam.db reindex
```

Suggested narration:

> The flow here is straightforward. I compile language into MIRL, optionally promote reusable symbols, and then rebuild the vector search layer so retrieval has fresh semantic coverage.

### Search and inspection commands

These commands are for operator-facing retrieval and debugging.

```powershell
python seam.py --db seam.db search "translator natural language" --budget 3
python seam.py --db seam.db stats
python seam.py --db seam.db trace clm:5
python seam.py --db seam.db pack clm:1,clm:2 --mode context
python seam.py --db seam.db decompile clm:1,clm:2 --mode expanded
python seam.py --db seam.db export-symbols
```

Suggested narration:

> Search is the obvious operator command, but the deeper story is that SEAM also gives me trace, context packing, decompilation, stats, and symbol export. So this is not just retrieval. It is a memory runtime with inspection tools around the retrieval loop.

### Embedding provider commands

These commands switch retrieval to an OpenAI-compatible embedding backend.

```powershell
$env:SEAM_EMBEDDING_PROVIDER="openai"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
$env:OPENAI_API_KEY="..."
python -m unittest test_seam.py
```

Suggested narration:

> By default, SEAM can run on deterministic local hash embeddings. If I want better semantic quality, I can switch providers through environment variables without changing MIRL or the higher-level runtime contract.

## 5. What the commands map to in code

This is useful if you want the video to feel technical instead of only operational.

### `python seam.py ...`

Routes through:

- `seam.py`
- then `seam_runtime/cli.py`
- then into `SeamRuntime` in `seam_runtime/runtime.py`

Suggested narration:

> seam.py is the public shell entrypoint, cli.py turns terminal flags into structured command dispatch, and runtime.py is where the actual system orchestration happens.

### `compile-nl`

Main code path:

- `seam_runtime/cli.py`
- `seam_runtime/runtime.py`
- `seam_runtime/nl.py`
- `seam_runtime/mirl.py`
- `seam_runtime/verify.py`
- `seam_runtime/storage.py` if `--persist` is used

### `reindex`

Main code path:

- `seam_runtime/runtime.py`
- `seam_runtime/storage.py`
- `seam_runtime/vector.py`
- `seam_runtime/vector_adapters.py`
- `seam_runtime/models.py`

### `search`

Main code path:

- `seam_runtime/runtime.py`
- `seam_runtime/retrieval.py`
- `seam_runtime/vector.py`
- `seam_runtime/vector_adapters.py`
- `seam_runtime/storage.py`

### `pack` and `decompile`

Main code path:

- `seam_runtime/runtime.py`
- `seam_runtime/pack.py`

### `promote-symbols` and `export-symbols`

Main code path:

- `seam_runtime/runtime.py`
- `seam_runtime/symbols.py`

### `trace`

Main code path:

- `seam_runtime/runtime.py`
- `seam_runtime/storage.py`

## 6. Canonical versus derived data

This is one of the most important concepts to explain in a video.

Suggested narration:

> The clean mental model is that SQLite is the source of truth for MIRL, provenance, packs, and metadata. The vector layer is acceleration, not truth. PACK is derived, not canonical. Symbols are derived, not canonical. That separation matters because it keeps search infrastructure from silently becoming the system of record.

Use this distinction:

### Canonical

- MIRL records
- provenance
- trace relationships
- stored metadata

### Derived

- vector index
- pgvector sidecar state
- pack outputs
- symbol export artifacts
- transpiled code

## 7. Recommended demo order

If you want the video to feel smooth, use this sequence.

### Segment 1: explain the repo

Show:

- `README.md`
- `docs/PROJECT_MAP.md`
- `docs/COMMANDS.md`
- `seam_runtime/`

Narration focus:

- what SEAM is
- what MIRL is
- where the code lives

### Segment 2: setup flow

Show:

- `.env.example`
- `scripts/setup-seam.ps1`
- `scripts/pgvector-up.ps1`
- `compose.yaml`

Narration focus:

- local setup is copy-paste
- password stays local in `.env`
- pgvector is bootstrapped from the repo

### Segment 3: basic CLI flow

Show:

- `python seam.py --help`
- `compile-nl`
- `reindex`
- `search`

Narration focus:

- language goes in
- MIRL gets created and stored
- vector layer gets refreshed
- hybrid retrieval comes back out

### Segment 4: advanced inspection

Show:

- `stats`
- `trace`
- `pack`
- `decompile`
- `export-symbols`

Narration focus:

- SEAM is inspectable
- records are traceable
- compact views can still be reasoned about

### Segment 5: architectural close

Narration focus:

- SQLite is canonical
- pgvector is acceleration
- retrieval is optimized for more useful context per token
- exact behavior stays exact where SEAM promises reversibility

## 8. Ready-to-read video script

Use this if you want a near-verbatim pass.

> In this video I want to show how SEAM is organized, what the main commands do, and how the repo is structured so the architecture is easy to follow. SEAM is a memory-first compiler and runtime for AI systems. The key distinction is that MIRL is the canonical memory representation, while PACK is the derived context view built from that memory.
>
> At the root of the repo, I have the operator layer. This is where the README lives, the main seam.py entrypoint, the main test file, the setup scripts, and the top-level docs. If I want to run SEAM from the command line, I start here.
>
> The actual system logic lives in seam_runtime. cli.py defines the commands, runtime.py orchestrates the system, nl.py and dsl.py compile inputs into MIRL, verify.py validates the result, storage.py persists the canonical records, retrieval.py handles hybrid ranking, vector.py and vector_adapters.py manage the semantic layer, pack.py builds derived context, and symbols.py manages machine-facing symbols.
>
> The docs folder holds the conceptual contracts. PROJECT_MAP explains where responsibilities live, COMMANDS gives me the operational command set, SOP_MODEL_INTEGRATION explains how embeddings and vector adapters fit in, and RETRIEVAL_EVAL_V1 explains how retrieval quality is judged.
>
> For setup, the main flow is to copy .env.example to .env, fill in the local Postgres values, and run the setup-seam PowerShell script. That installs Python dependencies, brings up the repo-owned pgvector Postgres service, enables the vector extension, and exports the session DSN without exposing the password in the terminal command.
>
> Once the environment is up, the first sanity checks are python seam.py --help and python -m unittest test_seam.py. The help command proves the CLI loads, and the test suite proves the runtime behavior is actually healthy.
>
> From there, the normal authoring flow is compile, reindex, and search. I can compile a natural-language instruction into MIRL, persist it, rebuild the vector index, and then run hybrid search over lexical, semantic, graph, and temporal signals.
>
> The deeper value in SEAM is that it also gives me inspection tools. I can trace a record, generate a packed context view, decompile records into an expanded form, inspect stats, and export symbols. So this is not just a search layer. It is a full memory runtime around the retrieval process.
>
> Architecturally, the most important rule is that SQLite remains the source of truth. MIRL, provenance, and metadata live there. The vector layer, including pgvector, is acceleration and retrieval infrastructure. PACK is derived. Symbols are derived. That separation keeps retrieval fast without turning the search backend into the canonical record system.
>
> So the simplest way to understand SEAM is this: language comes in, MIRL becomes the canonical record, storage preserves it, indexing makes it searchable, and PACK plus retrieval make it useful under real token budgets.

## 9. Optional closer

Suggested close:

> If you want to understand SEAM quickly, read the root docs, look at seam.py and runtime.py, and then follow the flow from compile to reindex to search. That path shows the whole shape of the system without getting lost in implementation detail.

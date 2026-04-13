# SEAM Operator Guide

This is the practical runbook for interacting with SEAM, running tests, and validating the live stack.

## 1. What SEAM uses

- SQLite for canonical truth, provenance, packs, and metadata
- SQLite `vector_index` by default for local vector search
- Optional Postgres + pgvector for a real external vector database
- Configurable embedding model:
  - default local deterministic hash model
  - optional OpenAI-compatible cloud embedding provider

## 2. Where the databases live

- SQLite truth database: whatever you pass to `--db`
  - examples: `seam.db`, `seam_validate.db`, `seam_live.db`, `seam_demo.db`
- SQLite vector index:
  - stored inside that same SQLite file unless pgvector is enabled
- pgvector database:
  - separate Postgres container
  - local validated DSN: `postgresql://postgres:postgres@localhost:54329/seam`
  - container name used so far: `seam-pgvector`

## 3. Environment setup

### Local deterministic baseline

No API key required.

```powershell
python seam.py --db seam_validate.db validate-stack
python seam.py --db seam_validate.db stats
```

### Live cloud + pgvector path

```powershell
$env:OPENAI_API_KEY="your-real-openai-api-key"
$env:SEAM_EMBEDDING_PROVIDER="openai-compatible"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
$env:SEAM_PGVECTOR_DSN="postgresql://postgres:postgres@localhost:54329/seam"

python seam.py --db seam_validate.db validate-stack
python seam.py --db seam_validate.db stats
```

### Start the local pgvector database

```powershell
docker run -d --name seam-pgvector -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=seam -p 54329:5432 pgvector/pgvector:pg17
```

If it already exists:

```powershell
docker start seam-pgvector
```

## 4. CLI surface

Top-level help:

```powershell
python seam.py --help
```

Available commands:

```text
ingest
compile-nl
compile-dsl
verify
persist
search
pack
decompile
trace
reconcile
transpile
reindex
promote-symbols
export-symbols
stats
validate-stack
```

## 5. How to interact with SEAM

### Compile natural language into MIRL

Compile only:

```powershell
python seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows."
```

Compile and persist:

```powershell
python seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows." --persist
```

### Compile DSL into MIRL

```powershell
python seam.py --db seam.db compile-dsl docs\example.dsl --persist
```

### Verify MIRL from a file

```powershell
python seam.py --db seam.db verify docs\example.mirl
```

### Persist MIRL from a file

```powershell
python seam.py --db seam.db persist docs\example.mirl
```

### Search persisted memory

```powershell
python seam.py --db seam.db search "translator natural language" --budget 3
python seam.py --db seam.db search "thread memory mode" --scope thread --budget 5
```

### Build packs

```powershell
python seam.py --db seam.db pack clm:2,sta:ent:project:seam --mode context --lens general --budget 128
python seam.py --db seam.db pack clm:2,sta:ent:project:seam --mode exact --lens general --budget 128
```

### Decompile records

```powershell
python seam.py --db seam.db decompile clm:2,sta:ent:project:seam
```

### Trace provenance

```powershell
python seam.py --db seam.db trace clm:2
```

### Reconcile contradictions or duplicates

```powershell
python seam.py --db seam.db reconcile
python seam.py --db seam.db reconcile --record-ids clm:truth:v1,clm:truth:v2
```

### Transpile workflows

```powershell
python seam.py --db seam.db transpile flow:search:1
python seam.py --db seam.db transpile flow:search:1 --target python
```

### Reindex vectors

```powershell
python seam.py --db seam.db reindex
python seam.py --db seam.db reindex --record-ids clm:2,sta:ent:project:seam
```

### Promote machine-only symbols

```powershell
python seam.py --db seam.db promote-symbols --min-frequency 1
python seam.py --db seam.db promote-symbols --record-ids clm:2,sta:ent:project:seam --min-frequency 1
```

### Export the symbol nursery

```powershell
python seam.py --db seam.db export-symbols
python seam.py --db seam.db export-symbols --namespace local.default --output docs\symbols.md
```

### Run benchmark summary

```powershell
python seam.py --db seam_validate.db stats
```

### Validate the embedding + pgvector stack

```powershell
python seam.py --db seam_validate.db validate-stack
```

## 6. Testing SEAM

### Run the full unit suite

```powershell
python -m unittest -v
```

### Run one specific test

```powershell
python -m unittest test_seam.SeamTests.test_retrieval_benchmark_uses_gold_fixtures -v
```

### Run a strict warning-sensitive test

```powershell
python -Werror::ResourceWarning -m unittest test_seam.SeamTests.test_symbol_export_and_query_expansion
```

### Recommended operator test loop

```powershell
python -m unittest -v
python seam.py --db seam_validate.db validate-stack
python seam.py --db seam_validate.db stats
```

Use the local baseline when you are changing core logic and want deterministic behavior.

Use the cloud path when you want a stronger teacher-quality embedding baseline.

## 7. Worked example

This is a real example flow you can run from a clean shell.

### Step 1: compile and persist one sentence

```powershell
python seam.py --db seam_demo.db compile-nl "We need a translator back into natural language for memory workflows." --persist
```

What happened:

- SEAM emitted `RAW`, `SPAN`, `PROV`, `ENT`, `CLM`, and `STA` records
- the important retrieval records included:
  - `clm:2` with predicate `translator`
  - `sta:ent:project:seam` with the translator field

### Step 2: search it

```powershell
python seam.py --db seam_demo.db search "translator natural language" --budget 3
```

Expected behavior:

- top result should include `clm:2`
- the search result should show reasons such as lexical, semantic, graph, and temporal contributions
- the evidence chain should include `span:1`

### Step 3: run one benchmark test

```powershell
python -m unittest test_seam.SeamTests.test_retrieval_benchmark_uses_gold_fixtures -v
```

Expected behavior:

- the test should pass
- it confirms the hardened fixture benchmark is loading and checking the current success gates

## 8. How to connect your own model

SEAM expects an embedding model with:

```python
name: str
dimension: int
embed(text: str) -> list[float]
```

Minimal example:

```python
from seam import SeamRuntime


class MyEmbeddingModel:
    name = "my-local-model"
    dimension = 768

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Replace with your model call")


runtime = SeamRuntime("seam.db", embedding_model=MyEmbeddingModel())
```

For a shell-based OpenAI-compatible path, use:

```powershell
$env:OPENAI_API_KEY="your-real-openai-api-key"
$env:SEAM_EMBEDDING_PROVIDER="openai-compatible"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
```

## 9. What to do when something fails

- `validate-stack` says API key missing:
  - set `OPENAI_API_KEY` in the same shell session
- `validate-stack` says pgvector DSN missing:
  - set `SEAM_PGVECTOR_DSN`
- `validate-stack` reports `HTTP 429`:
  - provider wiring is working, but quota/rate/billing needs attention
- `stats` regresses:
  - inspect the fixture-level `expected_ids`, `rejected_ids`, and `rejection_rate`
- search finds the right thing but also stale junk:
  - add or strengthen a benchmark fixture instead of relying on memory

## 10. Files worth knowing

- `README.md`
- `docs/BENCHMARK_SOP.md`
- `docs/RETRIEVAL_EVAL_V1.md`
- `docs/SOP_MODEL_INTEGRATION.md`
- `docs/PGVECTOR_LOCAL.md`
- `docs/ENGINEERING_LOG.md`
- `docs/retrieval_gold_fixtures.json`
- `test_seam.py`

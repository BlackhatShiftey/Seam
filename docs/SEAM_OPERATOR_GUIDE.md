# SEAM Operator Guide

Practical runbook for interacting with SEAM, running tests, and validating the
live stack.

## 1. What SEAM uses

- SQLite for canonical truth, provenance, packs, and metadata
- SQLite `vector_index` by default for local vector search
- Optional Postgres + pgvector for a real external vector database (port 55432)
- Configurable embedding model:
  - default local deterministic hash model (no credentials needed)
  - optional OpenAI-compatible cloud embedding provider

## 2. Where the databases live

- **SQLite truth database** - whatever you pass to `--db` (e.g. `seam.db`, `seam_validate.db`)
- **SQLite vector index** - stored inside that same SQLite file unless pgvector is enabled
- **pgvector database** - separate Postgres container `seam-pgvector` on `localhost:55432`

## 3. Environment setup

### Local deterministic baseline (no API key)

```powershell
python seam.py doctor
python seam.py --db seam_validate.db stats
```

### Live cloud + pgvector path

Credentials stay in a private env file outside the repo:

```powershell
$env:OPENAI_API_KEY="your-real-openai-api-key"
$env:SEAM_EMBEDDING_PROVIDER="openai-compatible"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
$env:SEAM_PGVECTOR_DSN="host=localhost port=55432 dbname=seam user=postgres password=$env:PGPASSWORD"

python seam.py doctor
python seam.py --db seam_validate.db stats
```

### Start the local pgvector database

```powershell
docker compose --env-file <path-to-private-env> up -d seam-pgvector
```

Image: `pgvector/pgvector:0.8.2-pg18-trixie` | Port: `55432`

If the container exists but is stopped:

```powershell
docker start seam-pgvector
```

## 4. CLI surface

```powershell
python seam.py --help
```

Key command groups:

| Command | What it does |
|---|---|
| `compile-nl` / `remember` | Compile natural language into MIRL and persist |
| `compile-dsl` | Compile SEAM DSL into MIRL and persist |
| `ingest` | Store raw text from a file or stdin |
| `verify` | Verify MIRL from a text file |
| `persist` | Persist MIRL from a text file |
| `search` | Combined search over persisted MIRL |
| `retrieve` / `hybrid-search` | Run retrieval and rank results |
| `memory` | Progressive-disclosure memory tools |
| `context` / `rag-search` | Retrieve context for generation |
| `index` / `rag-sync` | Sync persisted records into vector indexes |
| `pack` | Build a pack from persisted record IDs |
| `decompile` | Decompile persisted record IDs |
| `trace` | Trace provenance for an object ID |
| `reconcile` | Reconcile claims and emit relation/state updates |
| `stats` | Run the glassbox benchmark summary |
| `doctor` | Check install health and run smoke test |
| `benchmark` | Run or inspect SEAM benchmark suites |
| `surface` | Read/write SEAM-HS/1 holographic memory surfaces |
| `shell` / `chat` | Start an interactive SEAM memory REPL |
| `dashboard` | Launch the Textual terminal dashboard |
| `serve` | Run the SEAM REST API server |
| `mcp` | Run the SEAM agent MCP bridge |

## 5. How to interact with SEAM

### Compile natural language into MIRL and persist

```powershell
python seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows."
```

Use `--no-persist` to compile without storing.

### Search persisted memory

```powershell
python seam.py --db seam.db search "translator natural language" --budget 3
python seam.py --db seam.db search "thread memory mode" --scope thread --budget 5
```

### Retrieve with ranking

```powershell
python seam.py --db seam.db retrieve "translator natural language" --mode mix
python seam.py --db seam.db retrieve "translator natural language" --mode vector
python seam.py --db seam.db retrieve "translator natural language" --mode graph
```

### Sync vector indexes

```powershell
python seam.py --db seam.db index
```

### Build packs

```powershell
python seam.py --db seam.db pack clm:2,sta:ent:project:seam --mode context --budget 128
python seam.py --db seam.db pack clm:2,sta:ent:project:seam --mode exact --budget 128
```

### Decompile and trace

```powershell
python seam.py --db seam.db decompile clm:2,sta:ent:project:seam
python seam.py --db seam.db trace clm:2
```

### Check install health

```powershell
python seam.py doctor
```

### Interactive shell

```powershell
python seam.py shell
```

## 6. Testing SEAM

### Run the full suite

```powershell
python -m pytest test_seam_all\test_seam.py -q
```

### Run one specific test

```powershell
python -m pytest test_seam_all\test_seam.py -k "test_retrieval_benchmark_uses_gold_fixtures" -v
```

### Run with strict ResourceWarning detection

```powershell
python -W error::ResourceWarning -m pytest test_seam_all\test_seam.py -k "test_symbol_export_and_query_expansion" -v
```

### Recommended operator test loop

```powershell
python -m pytest test_seam_all\test_seam.py -q
python seam.py doctor
python seam.py --db seam_validate.db stats
```

Use the local baseline when changing core logic. Use the cloud path when
validating real embedding behavior.

## 7. Worked example

### Step 1: compile and persist

```powershell
python seam.py --db seam_demo.db compile-nl "We need a translator back into natural language for memory workflows."
```

SEAM emits `RAW`, `SPAN`, `PROV`, `ENT`, `CLM`, and `STA` records. Key retrieval
records include `clm:2` (predicate `translator`) and `sta:ent:project:seam`.

### Step 2: search

```powershell
python seam.py --db seam_demo.db search "translator natural language" --budget 3
```

Top result should include `clm:2`. Results show lexical, semantic, graph, and
temporal contribution reasons. Evidence chain includes `span:1`.

### Step 3: run one benchmark test

```powershell
python -m pytest test_seam_all\test_seam.py -k "test_retrieval_benchmark_uses_gold_fixtures" -v
```

Should pass and confirm the hardened fixture benchmark loads and checks current
success gates.

## 8. How to connect your own embedding model

SEAM expects a model with:

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

For the OpenAI-compatible cloud path:

```powershell
$env:OPENAI_API_KEY="your-real-openai-api-key"
$env:SEAM_EMBEDDING_PROVIDER="openai-compatible"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
```

## 9. What to do when something fails

| Symptom | Fix |
|---|---|
| `doctor` says API key missing | Set `OPENAI_API_KEY` in the same shell session |
| `doctor` says pgvector DSN missing | Set `SEAM_PGVECTOR_DSN` |
| `doctor` reports `HTTP 429` | Provider is reachable; check quota/billing |
| `stats` regresses | Inspect fixture-level `expected_ids`, `rejected_ids`, `rejection_rate` |
| Search returns stale results | Add or strengthen a benchmark fixture |
| Port 55432 refused | Run `docker ps` and check `seam-pgvector` is running |

## 10. Files worth knowing

- `README.md`
- `docs/setup.md`
- `docs/BENCHMARK_SOP.md`
- `docs/PGVECTOR_LOCAL.md`
- `docs/ENGINEERING_LOG.md`
- `docs/RETRIEVAL_EVAL_V1.md`
- `docs/SOP_MODEL_INTEGRATION.md`
- `docs/retrieval_gold_fixtures.json`
- `test_seam_all/test_seam.py`

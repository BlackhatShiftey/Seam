# SEAM

SEAM is a memory-first compiler/runtime for AI systems.

- `SEAM` = platform/runtime/CLI/SDK/adapters
- `MIRL` = canonical memory IR inside SEAM
- `PACK` = derived prompt-time view

## Current capabilities

- compile natural language into MIRL
- compile a narrow DSL into MIRL
- verify MIRL schema and exact-pack reversibility
- persist MIRL, provenance, raw evidence, and packs into SQLite
- index MIRL records for semantic search
- run hybrid search over lexical + vector + graph + temporal signals
- propose machine-only symbols and use them in compact packs
- reconcile duplicate or conflicting claims
- transpile memory workflows to Python stubs

## CLI quick start

```powershell
python seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows." --persist
python seam.py --db seam.db promote-symbols --min-frequency 1
python seam.py --db seam.db reindex
python seam.py --db seam.db search "translator natural language" --budget 3
python seam.py --db seam.db stats
python seam.py --db seam.db export-symbols
```

## Live stack validation

Validate the currently configured embedding provider and pgvector path:

```powershell
python seam.py --db seam_validate.db validate-stack
```

Typical live stack flow:

```powershell
docker run -d --name seam-pgvector -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=seam -p 54329:5432 pgvector/pgvector:pg17
$env:OPENAI_API_KEY="your-key"
$env:SEAM_EMBEDDING_PROVIDER="openai-compatible"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
$env:SEAM_PGVECTOR_DSN="postgresql://postgres:postgres@localhost:54329/seam"
python seam.py --db seam_validate.db validate-stack
python seam.py --db seam_validate.db stats
```

## Model configuration

Default:

- deterministic local hash embeddings

Environment-driven cloud embeddings:

```powershell
$env:SEAM_EMBEDDING_PROVIDER="openai-compatible"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
$env:OPENAI_API_KEY="your-key"
```

Optional pgvector DSN:

```powershell
$env:SEAM_PGVECTOR_DSN="postgresql://postgres:postgres@localhost:54329/seam"
```

Then:

```python
from seam import SeamRuntime

runtime = SeamRuntime("seam.db")
```

To plug in your own model, implement the embedding contract in `seam_runtime/models.py` terms:

```python
class MyEmbeddingModel:
    name = "my-local-model"
    dimension = 768

    def embed(self, text: str) -> list[float]:
        ...
```

Then:

```python
runtime = SeamRuntime("seam.db", embedding_model=MyEmbeddingModel())
```

## Storage blueprint

Canonical truth:

- `RAW`
- `SPAN`
- `PROV`
- MIRL records

Derived:

- `PACK`
- vector index in SQLite or pgvector
- symbol nursery export
- transpiled code

SQLite tables:

- `raw_docs`
- `raw_spans`
- `ir_records`
- `ir_edges`
- `symbol_table`
- `pack_store`
- `prov_log`
- `vector_index`

## Where The Databases Live

- SQLite truth store: the file you pass with `--db`, such as `seam.db`, `seam_validate.db`, or `seam_live.db`
- SQLite vector index: stored inside that same SQLite file unless you enable pgvector
- pgvector database: a separate Postgres container on `localhost:54329`, database `seam`, usually started as `seam-pgvector`

## Important docs

- [docs/ENGINEERING_LOG.md](docs/ENGINEERING_LOG.md)
- [docs/BENCHMARK_SOP.md](docs/BENCHMARK_SOP.md)
- [docs/MIRL_V1.md](docs/MIRL_V1.md)
- [docs/RETRIEVAL_EVAL_V1.md](docs/RETRIEVAL_EVAL_V1.md)
- [docs/SOP_MODEL_INTEGRATION.md](docs/SOP_MODEL_INTEGRATION.md)
- [docs/PGVECTOR_LOCAL.md](docs/PGVECTOR_LOCAL.md)
- [docs/SYMBOL_NURSERY.md](docs/SYMBOL_NURSERY.md)

# SOP: Plugging Models Into SEAM

This SOP explains how models connect to SEAM for:

- embedding generation
- semantic search
- NL compilation support
- pack/decompile workflows

## 1. Current architecture

SEAM uses one canonical storage layer and one optional vector acceleration layer:

- **SQLite** is the source of truth for MIRL, provenance, packs, and metadata
- **SQLite `vector_index`** is the default semantic index when you do not provide pgvector
- **pgvector/Postgres** is an optional external semantic index when you provide `SEAM_PGVECTOR_DSN`

The runtime flow is:

1. compile NL or DSL into MIRL
2. verify MIRL
3. persist MIRL into SQLite
4. index searchable MIRL records into `vector_index`
5. search by combining:
   - lexical match
   - vector similarity
   - graph expansion
   - temporal weighting

## 2. Current model hook points

The model integration layer lives in:

- `seam_runtime/models.py`
- `seam_runtime/runtime.py`
- `seam_runtime/vector.py`
- `seam_runtime/vector_adapters.py`

SEAM currently supports:

- `HashEmbeddingModel`
  - local deterministic fallback
  - no network required
  - good for tests and baseline retrieval

- `OpenAICompatibleEmbeddingModel`
  - uses an OpenAI-compatible embeddings endpoint
  - requires an API key
  - intended for real semantic quality

Use the local fallback when:

- you want deterministic tests
- you are working offline
- you are changing MIRL or retrieval logic and do not want cloud noise

Use cloud embeddings when:

- you want a teacher-quality retrieval baseline
- you are validating the live stack
- you want to compare future local OSS models against a stronger reference

## 3. Standard model contract

Any embedding model plugged into SEAM must provide:

```python
name: str
dimension: int
embed(text: str) -> list[float]
```

This means you can add:

- OpenAI embeddings
- local sentence-transformer style models
- Ollama-compatible embedding services
- self-hosted HTTP embedding endpoints

without changing MIRL or storage contracts.

## 4. How to plug in a new embedding model

### Option A: local deterministic default

Use the runtime as-is:

```python
from seam import SeamRuntime

runtime = SeamRuntime("seam.db")
```

This uses `HashEmbeddingModel`.

### Option B: OpenAI-compatible endpoint from the shell

Set the environment in the same shell where you run SEAM:

```powershell
$env:OPENAI_API_KEY="your-key"
$env:SEAM_EMBEDDING_PROVIDER="openai-compatible"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
$env:SEAM_PGVECTOR_DSN="postgresql://postgres:postgres@localhost:54329/seam"
```

Then validate:

```powershell
python seam.py --db seam_validate.db validate-stack
python seam.py --db seam_validate.db stats
```

Or instantiate the runtime directly:

```python
from seam import SeamRuntime
from seam_runtime.models import OpenAICompatibleEmbeddingModel

model = OpenAICompatibleEmbeddingModel(model="text-embedding-3-small")
runtime = SeamRuntime("seam.db", embedding_model=model)
```

### Option C: custom model

Implement the protocol:

```python
class MyEmbeddingModel:
    name = "my-embeddings-v1"
    dimension = 768

    def embed(self, text: str) -> list[float]:
        ...
```

Then:

```python
runtime = SeamRuntime("seam.db", embedding_model=MyEmbeddingModel())
```

If you want the runtime to use your model without wiring it manually each time, add your provider to `default_embedding_model()` and the env parser in `seam_runtime/models.py`.

## 5. Operational workflow

### Initial indexing

Persisting MIRL automatically indexes vector-searchable records.

To rebuild the vector index later:

```powershell
python seam.py --db seam.db reindex
```

To reindex a subset:

```powershell
python seam.py --db seam.db reindex --record-ids clm:1,sta:ent:project:seam
```

### Search

Search already uses the vector layer automatically:

```powershell
python seam.py --db seam.db search "translator natural language" --budget 5
```

The hybrid score combines:

- lexical score
- vector similarity
- graph expansion
- temporal weighting

## 6. Database wiring blueprint

SEAM uses SQLite as the coordination database and optional Postgres/pgvector for external vector search.

Database locations:

- SQLite truth store: whichever `--db` file you pass, such as `seam.db`, `seam_validate.db`, or `seam_live.db`
- pgvector store: the Postgres database named `seam` behind `SEAM_PGVECTOR_DSN`

Primary tables:

- `raw_docs`
- `raw_spans`
- `ir_records`
- `ir_edges`
- `symbol_table`
- `pack_store`
- `prov_log`
- `vector_index`

Wiring responsibilities:

- `ir_records` stores canonical MIRL JSON
- `ir_edges` stores graph relationships and trace edges
- `vector_index` stores searchable embedding vectors keyed by `record_id`

This means semantic search and relational/provenance search stay aligned through record ids.

## 7. Recommended production pattern

For production:

1. keep SQLite or Postgres as the canonical MIRL store
2. keep vectors in either:
   - SQLite `vector_index` for local/single-node usage
   - a dedicated vector DB adapter for scale
3. always use record ids as the join key between MIRL and vectors
4. never treat vectors as source of truth

Recommended future adapter order:

1. SQLite vector index
2. Postgres + pgvector adapter
3. external vector DB adapter

## 10. Pgvector-ready wiring

SEAM now has a `PgVectorAdapter` scaffold in:

- `seam_runtime/vector_adapters.py`

Runtime example:

```python
from seam import SeamRuntime, OpenAICompatibleEmbeddingModel

model = OpenAICompatibleEmbeddingModel(model="text-embedding-3-small")
runtime = SeamRuntime(
    "seam.db",
    embedding_model=model,
    pgvector_dsn="postgresql://user:pass@localhost:5432/seam",
)
```

Current status:

- SQLite vector adapter is fully active
- Pgvector adapter is active for production-style integration
- both adapters use the same MIRL record ids as join keys
- `validate-stack` can smoke-test the configured embedding provider and pgvector adapter
- the validated local pgvector setup is `postgresql://postgres:postgres@localhost:54329/seam`

## 8. What still needs to be completed

The current integration is functional, but still v1:

- add external vector DB adapters
- add embedding benchmark comparisons between cloud and local models
- add reranking model hooks
- add a stronger local embedding backend than the hash fallback
- formalize teacher-model to local-model data export for fine-tuning
- add first-class local OSS embedding model adapters under the same contract

## 9. Rule of thumb

If you are deciding where something belongs:

- **MIRL meaning** belongs in SQLite/Postgres canonical storage
- **semantic acceleration** belongs in the vector adapter
- **model choice** belongs in the embedding model implementation
- **search fusion** belongs in the runtime retrieval layer

That separation is the main thing that keeps SEAM clean.

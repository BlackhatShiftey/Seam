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
- run combined retrieval over lexical + vector + graph + temporal signals
- propose machine-only symbols and use them in compact packs
- reconcile duplicate or conflicting claims
- transpile memory workflows to Python stubs

## CLI quick start

```powershell
python seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows." --persist
python seam.py --db seam.db promote-symbols --min-frequency 1
python seam.py --db seam.db reindex
python seam.py --db seam.db search "translator natural language" --budget 3
python seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows." --index
python seam.py --db seam.db index
python seam.py --db seam.db plan "kind:CLM translator natural language" --budget 3
python seam.py --db seam.db retrieve "kind:CLM translator natural language" --budget 3 --trace
python seam.py --db seam.db retrieve "translator natural language" --vector-backend chroma --vector-path .seam_chroma --format json
python seam.py --db seam.db context "translator natural language" --format pretty
python seam.py --db seam.db context "translator natural language" --vector-backend chroma --vector-path .seam_chroma --format pretty
python seam.py --db seam.db compare "translator natural language" --budget 3
python seam.py --db seam.db export-symbols
```

## Environment setup

Create a local virtual environment and install the persistent vector backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

Then run the Chroma-backed RAG flow:

```powershell
python seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows." --index --vector-backend chroma
python seam.py --db seam.db context "translator natural language" --vector-backend chroma --format pretty
```

## Model configuration

Default:

- deterministic local hash embeddings

Environment-driven OpenAI-compatible embeddings:

```powershell
$env:SEAM_EMBEDDING_PROVIDER="openai"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
$env:OPENAI_API_KEY="..."
```

Then:

```python
from seam import SeamRuntime

runtime = SeamRuntime("seam.db")
```

## Storage blueprint

Canonical truth:

- `RAW`
- `SPAN`
- `PROV`
- MIRL records

Derived:

- `PACK`
- vector index
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

## Important docs

- [docs/MIRL_V1.md](C:/Users/iwana/OneDrive/Documents/Codex/docs/MIRL_V1.md:1)
- [docs/RETRIEVAL_EVAL_V1.md](C:/Users/iwana/OneDrive/Documents/Codex/docs/RETRIEVAL_EVAL_V1.md:1)
- [docs/SOP_MODEL_INTEGRATION.md](C:/Users/iwana/OneDrive/Documents/Codex/docs/SOP_MODEL_INTEGRATION.md:1)
- [docs/SYMBOL_NURSERY.md](C:/Users/iwana/OneDrive/Documents/Codex/docs/SYMBOL_NURSERY.md:1)

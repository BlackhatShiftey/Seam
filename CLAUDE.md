# CLAUDE.md — SEAM Codebase Guide

This file provides a comprehensive orientation for AI assistants (and developers) working in this repository. Read it fully before making any changes.

---

## Project Overview

**SEAM** is a memory-first compiler/runtime for AI systems. It defines a canonical memory representation called **MIRL** (Memory Intermediate Representation Language) and provides tooling to compile, persist, search, compress, verify, and transpile that memory.

Three core concepts:
- **SEAM** — the platform: runtime, CLI, SDK, adapters
- **MIRL** — the canonical memory IR stored inside SEAM
- **PACK** — a derived, prompt-time compressed view of MIRL records

---

## Repository Layout

```
/home/user/Seam/
├── seam.py                          # Public API facade + CLI entry point
├── test_seam.py                     # Full test suite (unittest)
├── SEAM_SPEC_V0.1.md                # Authoritative specification (1193 lines — read before changing IR)
├── seam_runtime/                    # Core implementation package
│   ├── __init__.py                  # Exported public types
│   ├── cli.py                       # 14-subcommand argparse CLI
│   ├── dsl.py                       # DSL compiler (structured text → MIRL)
│   ├── evals.py                     # Retrieval benchmark harness
│   ├── mirl.py                      # MIRL data types (RecordKind, MIRLRecord, IRBatch, Pack, …)
│   ├── models.py                    # Embedding model abstractions + env-driven factory
│   ├── nl.py                        # NL compiler (free text → MIRL)
│   ├── pack.py                      # Pack generation, unpacking, and scoring
│   ├── reconcile.py                 # Claim duplicate/contradiction resolution
│   ├── retrieval.py                 # Hybrid search (lexical + vector + graph + temporal)
│   ├── runtime.py                   # SeamRuntime orchestrator (main integration point)
│   ├── storage.py                   # SQLiteStore (8-table schema)
│   ├── symbols.py                   # Symbol proposal, maps, and markdown export
│   ├── transpile.py                 # MIRL → Python code generation
│   ├── vector.py                    # SQLiteVectorIndex
│   ├── vector_adapters.py           # Pluggable vector backends (SQLite, pgvector)
│   └── verify.py                    # Schema and reversibility validation
└── docs/
    ├── MIRL_V1.md                   # MIRL spec reference
    ├── RETRIEVAL_EVAL_V1.md         # Evaluation methodology
    ├── SOP_MODEL_INTEGRATION.md     # How to add/swap embedding models
    ├── SYMBOL_NURSERY.md            # Symbol allocation rules
    └── retrieval_gold_fixtures.json # Gold fixtures for benchmark tests
```

---

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.10+ |
| Database | SQLite (primary); PostgreSQL + pgvector (optional) |
| Embeddings | `HashEmbeddingModel` (default, local, deterministic); `OpenAICompatibleEmbeddingModel` (optional) |
| Test framework | `unittest` (stdlib) |
| External deps | None required — optional `psycopg` for pgvector |
| Build system | None; run directly with `python seam.py` |

There is no `requirements.txt`, `setup.py`, or `pyproject.toml`. All required dependencies are standard library. Keep it that way unless there is a compelling reason to add an external dependency.

---

## Architecture: Four Layers

```
┌───────────────────────────────────────────────────────────────┐
│  Orchestration   SeamRuntime (runtime.py) + CLI (cli.py)     │
├───────────────────────────────────────────────────────────────┤
│  Compilation     nl.py (NL→MIRL)  │  dsl.py (DSL→MIRL)      │
├───────────────────────────────────────────────────────────────┤
│  Data Model      mirl.py — RecordKind, MIRLRecord, IRBatch   │
│                  pack.py — Pack (compressed prompt views)     │
├───────────────────────────────────────────────────────────────┤
│  Processing      verify.py │ reconcile.py │ symbols.py       │
│                  retrieval.py │ vector.py │ vector_adapters.py│
│                  storage.py (SQLiteStore, 8 tables)           │
└───────────────────────────────────────────────────────────────┘
```

Data flows in one direction: **compile → verify → persist → index → search/pack**.

---

## Key Data Types (mirl.py)

### RecordKind (enum)
```
RAW  SPAN  ENT  CLM  EVT  REL  STA  SYM  PACK  FLOW  PROV  META
```

### Status (enum)
```
asserted  observed  inferred  hypothetical
contradicted  superseded  deprecated  deleted_soft
```

### MIRLRecord (dataclass)
Core fields: `id`, `kind`, `ns`, `scope`, `ver`, `created_at`, `updated_at`, `conf`, `status`, `t0`, `t1`, `prov`, `evidence`, `ext`, `attrs`

- `id` format: `{kind_lower}:{sequential_integer}` (e.g., `clm:1`, `ent:2`)
- `ns` format: dot-separated namespace hierarchy (e.g., `org.app.user.thread`)
- `conf` range: `0.0`–`1.0`
- `prov` / `evidence`: lists of record IDs linking to PROV and SPAN records

### IRBatch (dataclass)
Container for `list[MIRLRecord]`. Supports:
- `to_text()` / `from_text()` — pipe-delimited line format
- `to_json()` / `from_json()` — full JSON

### Pack (dataclass)
Compressed prompt view. Three modes:
- `exact` — fully reversible JSON; `unpack_exact_pack(pack)` returns the original `IRBatch`
- `context` — symbol-substituted compaction (irreversible but traceable)
- `narrative` — human-readable summary

---

## SeamRuntime API (runtime.py)

`SeamRuntime` is the primary integration point. Instantiate it with a SQLite path:

```python
from seam import SeamRuntime
runtime = SeamRuntime("seam.db")
```

| Method | Purpose |
|---|---|
| `compile_nl(text, ...)` | Free text → `IRBatch` |
| `compile_dsl(text, ...)` | DSL text → `IRBatch` |
| `verify_ir(batch)` | Returns `VerifyReport` |
| `persist_ir(batch)` | Validates, normalizes, writes to DB + vector index |
| `search_ir(query, ...)` | Hybrid search → `SearchResult` |
| `pack_ir(record_ids, ...)` | Build `Pack` from stored records |
| `decompile_ir(record_ids, ...)` | Human-readable MIRL summary |
| `trace(obj_id)` | Provenance graph → `TraceGraph` |
| `reconcile_ir(record_ids)` | Detect/resolve duplicate or conflicting claims |
| `transpile_ir(record_ids, target)` | MIRL → Python stub (`Artifact`) |
| `promote_symbols(min_frequency)` | Propose and persist machine symbols |
| `export_symbols(namespace, output_path)` | Symbol nursery markdown |
| `reindex_vectors(record_ids)` | Rebuild vector index |
| `run_retrieval_benchmark()` | Gold fixture evaluation → `dict` |

`persist_ir()` always validates before writing. If `VerifyReport.valid` is `False`, it raises `ValueError`.

---

## Public API (seam.py)

`seam.py` is the thin facade used in tests and user code:

```python
from seam import (
    SeamRuntime,
    compile_nl,      # → IRBatch
    compile_dsl,     # → IRBatch
    pack_ir,         # (batch_or_records, lens, budget, mode) → Pack
    decompile_ir,    # (batch_or_records, mode) → str
    render_ir,       # (batch_or_records) → str (pipe-delimited text)
    load_ir_lines,   # (text) → list[MIRLRecord]
    unpack_pack,     # (Pack) → dict or json
    verify_ir,       # (batch) → VerifyReport
)
```

---

## CLI Reference (cli.py)

Entry point: `python seam.py --db <path> <command> [args]`

| Subcommand | What it does |
|---|---|
| `ingest <source>` | Store raw text from file or stdin |
| `compile-nl <text> [--persist]` | NL → MIRL; optionally persists |
| `compile-dsl <file> [--persist]` | DSL file → MIRL |
| `verify <file>` | Validate MIRL from text file |
| `persist <file>` | Persist MIRL from text file |
| `search <query> [--scope] [--budget]` | Hybrid search |
| `pack <record_ids> [--lens] [--budget] [--mode]` | Build pack |
| `decompile <record_ids> [--mode]` | Decompile to text |
| `trace <obj_id>` | Provenance trace |
| `reconcile [--record-ids]` | Reconcile claims |
| `transpile <record_ids> [--target]` | MIRL → Python |
| `reindex [--record-ids]` | Rebuild vector index |
| `promote-symbols [--min-frequency]` | Propose/persist symbols |
| `export-symbols [--namespace] [--output]` | Symbol nursery markdown |
| `stats` | Run retrieval benchmark |

All commands output JSON or pipe-delimited MIRL text to stdout.

---

## Storage Schema (storage.py)

Eight SQLite tables:

| Table | Contents |
|---|---|
| `raw_docs` | Original raw text with source_ref |
| `raw_spans` | Extracted text spans |
| `ir_records` | All MIRL records (JSON-serialized) |
| `ir_edges` | Provenance and evidence edges |
| `symbol_table` | Proposed machine-only symbols |
| `pack_store` | Stored packs |
| `prov_log` | Provenance log entries |
| `vector_index` | Embedded vectors (JSON float arrays) |

**Canonical truth:** `raw_docs`, `raw_spans`, `prov_log`, and `ir_records`.  
**Derived (can be rebuilt):** `pack_store`, `vector_index`, `symbol_table` exports.

---

## Hybrid Search Scoring (retrieval.py)

`search_batch()` combines four independent signals with fixed weights:

| Signal | Weight | Source |
|---|---|---|
| Lexical | 40% | Term overlap with record text fields |
| Semantic (vector) | 35% | Cosine similarity via embedding model |
| Graph expansion | 15% | Provenance/evidence link bonus |
| Temporal | 10% | Recency of record timestamps |

Symbol expansion is applied to the query before ranking. Results include a `reasons` list explaining each score contribution.

---

## Embedding Models (models.py)

Protocol: `name: str`, `dimension: int`, `embed(text: str) -> list[float]`

**Default (no config needed):** `HashEmbeddingModel` — deterministic 64-dim bag-of-words using SHA256. No external calls, works offline.

**OpenAI-compatible:** configured entirely via environment variables:

```bash
SEAM_EMBEDDING_PROVIDER="openai"              # or "openai-compatible"
SEAM_EMBEDDING_MODEL="text-embedding-3-small"
SEAM_EMBEDDING_BASE_URL="https://api.openai.com/v1/embeddings"
SEAM_EMBEDDING_API_KEY_ENV="OPENAI_API_KEY"   # name of the var holding the key
SEAM_EMBEDDING_TIMEOUT_S="30.0"
SEAM_EMBEDDING_DIMENSIONS="1536"              # optional
```

Then `OPENAI_API_KEY=sk-...` must be set.

`default_embedding_model()` reads these at construction time. To add a new backend, implement the `EmbeddingModel` protocol and wire it into `models.py`.

---

## Vector Adapters (vector_adapters.py)

Two backends implementing the `VectorAdapter` protocol:

- **`SQLiteVectorAdapter`** — default; stores float arrays in `vector_index` table
- **`PgVectorAdapter`** — PostgreSQL + pgvector; pass `pgvector_dsn` to `SeamRuntime`

To use pgvector:
```python
runtime = SeamRuntime("seam.db", pgvector_dsn="postgresql://user:pass@host/db")
```

---

## Symbol System (symbols.py)

Symbols are short machine-readable aliases for repeated expansions. They live in the namespace hierarchy and are stored as `SYM` records.

Predefined core symbols: `goal→gl`, `scope→sc`, `principle→pr`, `constraint→cs`, `memory→mem`, and others.

Namespace hierarchy: `org → org.app → org.app.user → org.app.user.thread`  
Child namespaces can shadow parent symbols.

**Workflow:**
```bash
python seam.py --db seam.db persist mirl_records.txt
python seam.py --db seam.db promote-symbols --min-frequency 2
python seam.py --db seam.db reindex
python seam.py --db seam.db pack <ids> --mode context
python seam.py --db seam.db export-symbols
```

---

## DSL Syntax (dsl.py)

Minimal structured format for authoring MIRL without writing raw JSON:

```
entity project "SEAM" as p1

claim c1:
  subject p1
  predicate supports
  object ["db", "rag", "ctx"]
  conf 0.9

state s1:
  subject p1
  fields status=active priority=high
```

Supported block types: `entity`, `claim`, `state`, `pack`

---

## Running Tests

```bash
cd /home/user/Seam
python -m unittest test_seam.py -v
```

Tests use a per-test temporary SQLite database (UUID-named, deleted in `tearDown`).

**Test coverage includes:**
- NL and DSL compilation → MIRL generation
- Exact pack round-trip reversibility
- Verifier rejection of invalid MIRL
- End-to-end persist → search → trace
- Vector index reindex and recall
- Symbol promotion and pack compaction
- Symbol export and query expansion
- Namespace chain inheritance
- Decompile output and pack payload structure
- Text parser round-trip (pipe-delimited format)
- Embedding model env-variable configuration
- Retrieval benchmark with gold fixtures
- Pack scoring metrics (reversibility, traceability)

There is no separate CI configuration. Run tests locally before committing.

---

## Code Conventions

- **Python 3.10+** — all files begin with `from __future__ import annotations`
- **Type annotations** — all functions and methods are fully typed
- **Naming:** `PascalCase` for classes, `snake_case` for functions/methods/variables, `UPPER_CASE` for module-level constants
- **Private helpers** — prefixed with `_` (e.g., `_lexical_score`, `_init_schema`)
- **Dataclasses** — used heavily; frozen where immutability is appropriate
- **Imports** — standard library first, then local relative imports (`from .module import X`)
- **Line length** — approximately 100–120 characters; no enforced formatter is configured
- **Docstrings** — minimal; functions are named to be self-documenting
- **No external formatters** — no `.black`, `.isort`, `.pylintrc`, or `pyproject.toml` present; maintain style consistency with existing code
- **No CI** — no `.github/workflows/` or other pipeline configuration exists

---

## Development Workflow

### Typical ingest → search cycle
```bash
# Compile and persist NL text
python seam.py --db seam.db compile-nl "Your text." --persist

# Rebuild symbols and vector index
python seam.py --db seam.db promote-symbols --min-frequency 2
python seam.py --db seam.db reindex

# Search
python seam.py --db seam.db search "your query" --budget 5

# Export symbol nursery for audit
python seam.py --db seam.db export-symbols
```

### Adding a new module
1. Create `seam_runtime/<module>.py` following the `from __future__ import annotations` convention
2. Add public types to `seam_runtime/__init__.py` if they form part of the public API
3. Wire into `SeamRuntime` (`runtime.py`) if the feature needs orchestration
4. Add a CLI subcommand in `cli.py` if user-facing
5. Add tests in `test_seam.py`

### Adding a new embedding backend
1. Implement the `EmbeddingModel` protocol in `models.py`
2. Add recognition logic in `default_embedding_model()` (env-variable driven)
3. Document the new `SEAM_EMBEDDING_PROVIDER` value in this file and in `docs/SOP_MODEL_INTEGRATION.md`
4. Add a test case in `test_seam.py`

---

## Important Rules for AI Assistants

1. **Read `SEAM_SPEC_V0.1.md` before modifying any IR data types.** It is the authoritative specification and defines field semantics, encoding rules, and invariants that must be preserved.

2. **Compilation modules (`nl.py`, `dsl.py`) only produce MIRL records.** They must not write to storage directly. Storage is exclusively `storage.py`'s responsibility.

3. **`persist_ir()` always validates first.** Never bypass `verify_ir()` when writing records. If validation fails, fix the records, not the validator.

4. **Pack modes have different reversibility guarantees:**
   - `exact` — fully reversible; `unpack_exact_pack()` must reconstruct the original `IRBatch` exactly
   - `context` — irreversible but traceable (traceability ≥ 0.66)
   - `narrative` — for human display only

5. **Do not add external dependencies** unless strictly necessary. The standard library is intentionally sufficient.

6. **Test data is ephemeral.** Tests create UUID-named SQLite files and delete them in `tearDown`. Do not rely on persistent test state.

7. **All search scoring weights are explicit.** Do not adjust the 40/35/15/10 split in `retrieval.py` without updating this document and the spec.

8. **Symbol IDs must not collide.** When proposing new predefined symbols in `symbols.py`, check against existing entries and follow the ambiguity-scoring logic.

9. **The `ir_records` table is canonical truth.** `pack_store`, `vector_index`, and symbol exports are all derived and can be rebuilt from `ir_records` at any time.

10. **Namespace format is `dotted.lowercase.string`.** Do not use slashes, uppercase, or spaces in namespace identifiers.

---

## Key Reference Documents

| Document | Purpose |
|---|---|
| `SEAM_SPEC_V0.1.md` | Authoritative IR specification (read before changing data types) |
| `docs/MIRL_V1.md` | MIRL specification reference |
| `docs/SOP_MODEL_INTEGRATION.md` | How to add or swap embedding models |
| `docs/SYMBOL_NURSERY.md` | Symbol allocation rules and namespace mechanics |
| `docs/RETRIEVAL_EVAL_V1.md` | Retrieval evaluation methodology and success criteria |
| `docs/retrieval_gold_fixtures.json` | Gold fixtures used by the benchmark harness |

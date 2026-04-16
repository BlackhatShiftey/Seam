# CLAUDE.md — SEAM Continuity Guide

This file is the Claude-facing resume guide for the SEAM repo.
It is **not** the canonical project ledger — durable memory lives in `PROJECT_STATUS.md` and `REPO_LEDGER.md`.

---

## Read Order on Resume

1. `PROJECT_STATUS.md` — short current snapshot, what is done, what still needs work, immediate next step
2. `REPO_LEDGER.md` — full engineering history, architecture decisions, active branch, milestone log
3. `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md` — if the task touches benchmarking, machine language, or evaluation policy
4. `benchmarks/README.md` — operator-facing benchmark commands
5. `experimental/retrieval_orchestrator/README.md` — if the task touches retrieval planning or orchestration

---

## Project Identity

- **SEAM** — machine-first memory compiler/runtime and operator glassbox for AI agents
- **MIRL** — canonical memory IR (Memory Intermediate Representation Language)
- **PACK** — derived prompt-time or context-time compressed view of MIRL
- **SEAM-LX/1** — exact machine-text envelope for lossless document compression and token-efficiency benchmarks

---

## Active Branch

`feature/hybrid-orchestrator-v2`

Handoff branch: `handoff/archive`

---

## Repository Layout

```
/
├── seam.py                          # Public API facade + CLI entry point
├── test_seam.py                     # Full test suite (unittest)
├── pyproject.toml                   # Build config; console scripts: seam, seam-benchmark
├── requirements.txt                 # chromadb, rich, tiktoken
├── SEAM_SPEC_V0.1.md                # Authoritative MIRL specification
├── PROJECT_STATUS.md                # Short current-state tracker (read first)
├── REPO_LEDGER.md                   # Long-form engineering memory (read second)
├── CLAUDE.md                        # This file
├── GEMINI.md                        # Gemini-facing resume guide
├── ANTIGRAVITY.md                   # Antigravity-facing resume guide
├── seam_runtime/                    # Core implementation package
│   ├── __init__.py                  # Exported public types
│   ├── benchmarks.py                # Six-family glassbox benchmark engine
│   ├── cli.py                       # Full CLI (30+ subcommands + aliases)
│   ├── context_views.py             # Context view rendering (pack/prompt/evidence/summary/records)
│   ├── dashboard.py                 # Runtime-connected terminal dashboard
│   ├── dsl.py                       # DSL compiler (structured text → MIRL)
│   ├── evals.py                     # Retrieval benchmark harness (gold fixtures)
│   ├── installer.py                 # Install path management, default DB path
│   ├── lossless.py                  # SEAM-LX/1 lossless compression/decompression engine
│   ├── mirl.py                      # MIRL data types (RecordKind, MIRLRecord, IRBatch, Pack…)
│   ├── models.py                    # Embedding model abstractions + env-driven factory
│   ├── nl.py                        # NL compiler (free text → MIRL)
│   ├── pack.py                      # Pack generation, unpacking, and scoring
│   ├── reconcile.py                 # Claim duplicate/contradiction resolution
│   ├── retrieval.py                 # Hybrid search (lexical + vector + graph + temporal)
│   ├── runtime.py                   # SeamRuntime orchestrator
│   ├── storage.py                   # SQLiteStore (12-table schema)
│   ├── symbols.py                   # Symbol proposal, maps, and markdown export
│   ├── transpile.py                 # MIRL → Python code generation
│   ├── vector.py                    # SQLiteVectorIndex
│   ├── vector_adapters.py           # Pluggable vector backends (SQLite, pgvector)
│   └── verify.py                    # Schema and reversibility validation
├── experimental/
│   ├── retrieval_orchestrator/      # Canonical retrieval planning package
│   │   ├── orchestrator.py          # RetrievalOrchestrator: plan/search/rag/sync
│   │   ├── planner.py               # Query classification + filter extraction
│   │   ├── adapters.py              # SQLiteIRAdapter, SeamVectorSearchAdapter, ChromaSemanticAdapter
│   │   ├── merger.py                # Hit normalization + reranking
│   │   └── types.py                 # RetrievalPlan, RetrievalSearchResult, RAGResult
│   └── hybrid_orchestrator/         # Compatibility alias layer (legacy imports resolve here)
├── benchmarks/
│   ├── SEAM_BENCHMARK_BLUEPRINT_V1.md
│   ├── README.md
│   └── fixtures/                    # agent_tasks.json, long_context_cases.json, lossless_cases.json
├── installers/                      # install_seam.py, install_seam_linux.sh, install_seam_windows.ps1
├── scripts/                         # bootstrap_seam.ps1, enter_seam.ps1, install_global_seam_command.ps1
├── tools/
│   └── lossless_demo_input.txt      # Demo input for lossless compression flows
├── branding/                        # SVG marks, screenshots, design principles, terminal preview
└── docs/
    ├── MIRL_V1.md
    ├── RETRIEVAL_EVAL_V1.md
    ├── SOP_MODEL_INTEGRATION.md
    ├── SYMBOL_NURSERY.md
    └── retrieval_gold_fixtures.json
```

---

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Database | SQLite (canonical); PostgreSQL + pgvector (optional) |
| Vector semantic backend | SQLite (default); Chroma (optional) |
| Embeddings | `HashEmbeddingModel` (default, local, deterministic); `OpenAICompatibleEmbeddingModel` (optional) |
| Tokenizer | `tiktoken` (preferred); `char4_approx` fallback |
| UI | `rich` (terminal rendering) |
| Test framework | `unittest` (stdlib) |
| Build | `pyproject.toml` (setuptools); console scripts `seam` and `seam-benchmark` |
| External deps | `chromadb`, `rich`, `tiktoken` (all optional at runtime, listed in `requirements.txt`) |

---

## Architecture: Five Layers

```
┌────────────────────────────────────────────────────────────────┐
│  Orchestration    SeamRuntime (runtime.py) + CLI (cli.py)      │
│                   RetrievalOrchestrator (experimental/)         │
│                   Dashboard (dashboard.py)                      │
├────────────────────────────────────────────────────────────────┤
│  Compilation      nl.py (NL→MIRL)  │  dsl.py (DSL→MIRL)       │
│  Compression      lossless.py (SEAM-LX/1)                      │
├────────────────────────────────────────────────────────────────┤
│  Data Model       mirl.py — RecordKind, MIRLRecord, IRBatch    │
│                   pack.py — Pack (compressed prompt views)      │
│                   context_views.py — operator-facing views      │
├────────────────────────────────────────────────────────────────┤
│  Processing       verify.py │ reconcile.py │ symbols.py        │
│                   retrieval.py │ benchmarks.py │ evals.py       │
│                   vector.py │ vector_adapters.py                │
├────────────────────────────────────────────────────────────────┤
│  Storage          storage.py (SQLiteStore, 12 tables)           │
│                   models.py (embedding backends)                │
└────────────────────────────────────────────────────────────────┘
```

Data flows one direction: **compile → verify → persist → index → search/pack/benchmark**

---

## Storage Schema (storage.py) — 12 Tables

**Canonical truth (never drop or skip):**

| Table | Contents |
|---|---|
| `raw_docs` | Original raw text with source_ref |
| `raw_spans` | Extracted text spans |
| `ir_records` | All MIRL records (JSON-serialized) |
| `prov_log` | Provenance log entries |

**Derived (rebuildable):**

| Table | Contents |
|---|---|
| `ir_edges` | Provenance and evidence graph edges |
| `symbol_table` | Proposed machine-only symbols |
| `pack_store` | Stored packs |
| `vector_index` | Embedded vectors (JSON float arrays) |

**Machine / benchmark (new):**

| Table | Contents |
|---|---|
| `machine_artifacts` | Lossless compression artifacts and projections |
| `benchmark_runs` | Persisted benchmark suite run records |
| `benchmark_cases` | Per-case benchmark results |
| `projection_index` | Machine-projection derived indexes |

---

## CLI Reference

Entry point: `seam --db <path> <command>` or `python seam.py --db <path> <command>`

### Core MIRL commands

| Command | Purpose |
|---|---|
| `ingest <source>` | Store raw text from file or stdin |
| `compile-nl <text> [--persist] [--index]` | NL → MIRL |
| `compile-dsl <file> [--persist] [--index]` | DSL file → MIRL |
| `verify <file>` | Validate MIRL |
| `persist <file> [--index]` | Persist MIRL from text file |
| `search <query> [--scope] [--budget]` | Basic hybrid search |
| `pack <ids> [--lens] [--budget] [--mode]` | Build pack |
| `decompile <ids> [--mode]` | Decompile to text |
| `trace <obj_id>` | Provenance trace |
| `reconcile [--record-ids]` | Reconcile claims |
| `transpile <ids> [--target]` | MIRL → Python |
| `reindex [--record-ids]` | Rebuild vector index |
| `promote-symbols [--min-frequency]` | Propose/persist symbols |
| `export-symbols [--namespace] [--output]` | Symbol nursery markdown |
| `stats` | Run retrieval benchmark |

### Retrieval orchestrator commands

| Command | Aliases | Purpose |
|---|---|---|
| `plan <query>` | `hybrid-plan` | Build a retrieval plan |
| `retrieve <query>` | `hybrid-search` | Run retrieval and rank results |
| `compare <query>` | `hybrid-compare` | Compare basic search vs. retrieval |
| `index [--record-ids]` | `rag-sync` | Sync records into vector indexes |
| `context <query>` | `rag-search` | Retrieve context for generation |

### Lossless compression commands

| Command | Aliases | Purpose |
|---|---|---|
| `lossless-compress <source>` | `compress-doc` | Compress document to SEAM-LX/1 machine text |
| `lossless-decompress <source>` | `decompress-doc` | Restore original document from machine text |
| `lossless-benchmark <source>` | `benchmark-doc` | Benchmark compression + roundtrip |
| `demo lossless <src> <out>` | — | Operator demo: compress or `--rebuild` |

### Benchmark commands

| Command | Purpose |
|---|---|
| `benchmark run [suite] [--persist] [--output]` | Run benchmark suites (all or named family) |
| `benchmark show [run_id]` | Show a persisted run (`latest` by default) |
| `benchmark verify <bundle>` | Verify bundle hash and case hashes |

### Operator commands

| Command | Purpose |
|---|---|
| `dashboard [--snapshot] [--run <cmd>]` | Launch runtime-connected terminal dashboard |
| `doctor` | Install health check + smoke test |

**Benchmark suite families:** `lossless`, `retrieval`, `embedding`, `long_context`, `persistence`, `agent_tasks`

---

## Retrieval Orchestrator (experimental/)

**Canonical package:** `experimental.retrieval_orchestrator`
**Compat alias:** `experimental.hybrid_orchestrator` (legacy imports still resolve)

`RetrievalOrchestrator` wraps a `SeamRuntime` and provides:

| Method | Purpose |
|---|---|
| `plan(query, scope, budget)` | Classify query intent + extract filters → `RetrievalPlan` |
| `search(query, ...)` | Execute SQL + vector legs, merge, rank → `RetrievalSearchResult` |
| `rag(query, ...)` | Search + pack context → `RAGResult` |
| `sync_persistent_indexes(...)` | Sync records into SQLite vector index and optional Chroma |

Two semantic backends:
- **`seam`** (default) — `SeamVectorSearchAdapter` wrapping the SQLite vector index
- **`chroma`** — `ChromaSemanticAdapter` using a persistent Chroma collection

The SQL retrieval leg pushes field filters (`kind`, `scope`, `ns`, `predicate`, `subject`, `object`), lexical gating, and ranking into SQL — it is not an in-memory scan.

---

## SEAM-LX/1 Lossless Compression (lossless.py)

Machine-text format for exact document compression and token-efficiency benchmarking.

**Envelope format:**
```
SEAM-LX/1
c=<codec>
t=<transform>
h=<sha256>
p=<base85-encoded-payload>
```

**Codecs:** `zlib`, `bz2`, `lzma` (auto-selects best)
**Transforms:** `identity`, `line_table`, `paragraph_table`
**Token estimator:** `tiktoken` (cl100k_base or o200k_base) with `char4_approx` fallback

Decompression verifies SHA-256 integrity and raises `ValueError` on mismatch — any lossy result fails loudly.

**Public API (seam.py):**
```python
from seam import lossless_compress, lossless_decompress, lossless_benchmark
artifact = lossless_compress("your text")
original = lossless_decompress(artifact.machine_text)
result = lossless_benchmark("your text", min_token_savings=0.30)
```

---

## Context Views (context_views.py)

The `context` command and `RetrievalOrchestrator.rag()` support five output views:

| View | Output |
|---|---|
| `pack` | Compressed MIRL pack (default) |
| `prompt` | Formatted prompt-ready text with citations |
| `evidence` | Per-record citations with scores and provenance |
| `summary` | Record count, kind breakdown, highlights |
| `records` | Raw JSON records |

---

## SeamRuntime API (runtime.py)

```python
from seam import SeamRuntime
runtime = SeamRuntime("seam.db")
```

**Core methods (unchanged):**
`compile_nl`, `compile_dsl`, `verify_ir`, `normalize_ir`, `persist_ir`, `search_ir`, `pack_ir`, `decompile_ir`, `trace`, `reconcile_ir`, `transpile_ir`, `suggest_symbols`, `promote_symbols`, `export_symbols`, `reindex_vectors`, `run_retrieval_benchmark`

**New benchmark methods:**

| Method | Purpose |
|---|---|
| `run_benchmark_suite(suite, tokenizer, persist, ...)` | Run named or all benchmark families |
| `verify_benchmark_bundle(bundle)` | Verify bundle hash + case hashes |
| `read_benchmark_run(run_id)` | Load persisted run |
| `list_benchmark_runs(limit)` | List persisted runs |

---

## Key Data Types (mirl.py)

### RecordKind (12 kinds)
```
RAW  SPAN  ENT  CLM  EVT  REL  STA  SYM  PACK  FLOW  PROV  META
```

### Status (8 values)
```
asserted  observed  inferred  hypothetical
contradicted  superseded  deprecated  deleted_soft
```

### MIRLRecord
`id` format: `{kind_lower}:{integer}` — `id` field: `ns`, `scope`, `conf` (0–1), `status`, `t0`, `t1`, `prov`, `evidence`, `ext`, `attrs`

### Pack modes
- `exact` — fully reversible; `unpack_exact_pack()` reconstructs original `IRBatch`
- `context` — symbol-compacted (irreversible but traceable ≥ 0.66)
- `narrative` — human display only

---

## Embedding & Vector Backends

**Embedding models** (models.py) — env-driven:
```bash
SEAM_EMBEDDING_PROVIDER="openai"           # or "openai-compatible", default is "hash"
SEAM_EMBEDDING_MODEL="text-embedding-3-small"
SEAM_EMBEDDING_BASE_URL="https://api.openai.com/v1/embeddings"
SEAM_EMBEDDING_API_KEY_ENV="OPENAI_API_KEY"
SEAM_EMBEDDING_TIMEOUT_S="30.0"
SEAM_EMBEDDING_DIMENSIONS="1536"
```

**Vector adapters** — pass at construction:
```python
runtime = SeamRuntime("seam.db", pgvector_dsn="postgresql://user:pass@host/db")
```
Or use Chroma via the retrieval orchestrator (`--vector-backend chroma`).

---

## Running Tests

```bash
cd /home/user/Seam
python -m unittest test_seam.py -v
```

Tests use UUID-named SQLite files, deleted in `tearDown`. No CI is configured — run locally before committing.

---

## Code Conventions

- `from __future__ import annotations` at the top of every module
- Full type annotations on all functions and methods
- `PascalCase` classes, `snake_case` functions/variables, `UPPER_CASE` constants
- Private helpers prefixed `_`
- Relative imports within `seam_runtime` (`from .module import X`)
- No enforced formatter — maintain consistency with existing style
- Minimal docstrings; functions are named to be self-documenting
- No comments explaining what code does; only comment the non-obvious why

---

## Stable Architecture Decisions

These must not be reversed without explicit discussion:

1. **SQLite is canonical truth.** Chroma, vector indexes, packs, machine projections, and symbol exports are all derived and rebuildable from `ir_records`.
2. **Compilation modules never write to storage.** `nl.py` and `dsl.py` produce `IRBatch` only; `storage.py` owns all persistence.
3. **`persist_ir()` always validates first.** Never bypass `verify_ir()`. Fix the records, not the validator.
4. **Chroma is optional.** It must not become canonical. Use it as a derived semantic layer only.
5. **No lossy compression.** SEAM-LX/1 must always pass exact SHA-256 roundtrip verification.
6. **Benchmark claims require auditable bundles.** No wins claimed from screenshots alone — bundle hash + case hashes + fixture hashes required.
7. **Retrieval orchestrator stays in `experimental/`** until the benchmark engine proves retrieval quality holds under machine-projection changes.
8. **Search scoring weights are fixed** at lexical 40% / semantic 35% / graph 15% / temporal 10%. Do not adjust without updating `REPO_LEDGER.md` and the spec.
9. **Namespace format is `dotted.lowercase.string`.** No slashes, uppercase, or spaces.
10. **Read `SEAM_SPEC_V0.1.md` before modifying any IR data type.** It is the authoritative specification.

---

## Common Workflows

### Ingest → search
```bash
seam compile-nl "Your text." --persist --index
seam promote-symbols --min-frequency 2
seam context "your query" --view prompt
```

### Lossless demo
```bash
seam demo lossless tools/lossless_demo_input.txt compressed.seam-lx
seam demo lossless compressed.seam-lx rebuilt.txt --rebuild
```

### Benchmark run
```bash
seam benchmark run all --persist --output seam-benchmark-report.json
seam benchmark show latest
seam benchmark verify seam-benchmark-report.json
```

### Install health check
```bash
seam doctor
```

### Adding a new module
1. Create `seam_runtime/<module>.py` with `from __future__ import annotations`
2. Add public types to `seam_runtime/__init__.py` if part of the public API
3. Wire into `SeamRuntime` (`runtime.py`) if it needs orchestration
4. Add a CLI subcommand in `cli.py` if user-facing
5. Add tests in `test_seam.py`

---

## Security Rules — Non-Negotiable

1. **Never commit credentials.** API keys, passwords, tokens, private keys, and personal account details must never appear in any committed file.
2. **Use environment variables for secrets.** Reference by name only (e.g., `OPENAI_API_KEY`). Never hardcode values.
3. **No real values in examples.** Use placeholders: `sk-...`, `your-api-key`, `<YOUR_KEY_HERE>`.
4. **No personal account details.** No usernames, email addresses, personal tokens, or account IDs in committed files.
5. **`.env` files are always gitignored.** Do not override or work around this.
6. **Audit the diff before every commit.** If anything looks like a real credential, remove it.
7. **No session or conversation links anywhere.** No `claude.ai` URLs, session links, or conversation links in commit messages, PR descriptions, code, comments, or documentation. These expose private session content.

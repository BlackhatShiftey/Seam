# Project Map

## Root Files

- `README.md`: project overview, quick-start commands, storage blueprint
- `seam.py`: public Python entrypoint and convenience helpers
- `test_seam.py`: main unittest suite covering compile, pack, runtime, retrieval, symbols, and CLI parsing
- `SEAM_SPEC_V0.1.md`: broader spec snapshot

## Runtime Package

### Entry and orchestration

- `seam_runtime/cli.py`: argparse CLI definitions and command dispatch
- `seam_runtime/runtime.py`: `SeamRuntime` orchestration over compile, verify, persist, retrieval, packing, trace, and symbol flows

### Compilation and IR

- `seam_runtime/nl.py`: natural-language to MIRL compilation
- `seam_runtime/dsl.py`: DSL to MIRL compilation
- `seam_runtime/mirl.py`: MIRL record types, batches, reports, and serialization
- `seam_runtime/verify.py`: IR validation rules and report generation
- `seam_runtime/pack.py`: pack generation and exact unpacking
- `seam_runtime/transpile.py`: workflow transpilation hooks

### Retrieval and memory

- `seam_runtime/retrieval.py`: hybrid ranking and query-time assembly
- `seam_runtime/vector.py`: vector utilities
- `seam_runtime/vector_adapters.py`: SQLite and pgvector adapter layer
- `seam_runtime/reconcile.py`: reconciliation logic for conflicting or duplicate claims
- `seam_runtime/symbols.py`: symbol proposal, namespace handling, and export

### Persistence and model integration

- `seam_runtime/storage.py`: SQLite persistence and trace loading
- `seam_runtime/models.py`: embedding provider abstraction and defaults
- `seam_runtime/evals.py`: retrieval benchmark runner

## Existing Deep-Dive Docs

- `docs/MIRL_V1.md`: MIRL schema and concepts
- `docs/RETRIEVAL_EVAL_V1.md`: retrieval evaluation framing
- `docs/SOP_MODEL_INTEGRATION.md`: model and embedding integration notes
- `docs/SYMBOL_NURSERY.md`: symbol governance and export expectations

## Common Edit Paths

- New CLI behavior: `seam.py`, `seam_runtime/cli.py`, tests in `test_seam.py`
- Runtime behavior changes: `seam_runtime/runtime.py` plus targeted subsystem modules
- Retrieval tuning: `retrieval.py`, `vector.py`, `vector_adapters.py`, related docs
- Symbol or compaction changes: `symbols.py`, `pack.py`, `docs/SYMBOL_NURSERY.md`

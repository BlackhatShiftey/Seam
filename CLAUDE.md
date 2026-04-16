# CLAUDE.md - SEAM Continuity Guide

This file is the Claude-facing resume guide for the SEAM repo.
It is not the canonical project ledger.

## Read Order

1. `PROJECT_STATUS.md`
2. `REPO_LEDGER.md`
3. `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md` if the task touches benchmarking, machine language, or evaluation policy
4. `benchmarks/README.md` for operator-facing benchmark commands
5. `experimental/retrieval_orchestrator/README.md` if the task touches retrieval planning

## Repo Model

- `SEAM` is the machine-first runtime and operator glassbox
- `MIRL` is the canonical memory IR
- `PACK` is the derived prompt-time context view
- `SEAM-LX/1` is the exact machine-text envelope for lossless document compression
- SQLite is canonical truth
- Chroma and vector stores are derived retrieval layers

## Current Working Surface

Working branch: `feature/hybrid-orchestrator-v2`

Stable runtime surfaces:

- compile, verify, persist, search, trace, pack, reconcile, transpile, export symbols
- retrieval/context views: `pack`, `prompt`, `evidence`, `summary`, `records`
- benchmark engine: `benchmark run`, `benchmark show`, `benchmark verify`
- exact document demo: `demo lossless ...` and `--rebuild`
- installed terminal commands: `seam`, `seam-benchmark`

## Commands Worth Remembering

```text
seam doctor
seam benchmark run all --persist --output seam-benchmark-report.json
seam benchmark show latest
seam benchmark verify seam-benchmark-report.json
seam demo lossless <source> <output> --min-savings 0.75
seam demo lossless <machine> <output> --rebuild
```

## Important Rules

- do not make Chroma canonical
- do not accept lossy compression
- do not claim benchmark wins without bundle verification
- keep `PROJECT_STATUS.md` and `REPO_LEDGER.md` updated when the direction changes
- treat this file as a resume guide only; durable memory lives elsewhere

## Next Useful Work

- benchmark natural vs machine vs hybrid retrieval projections
- validate the Linux installer on a real machine
- deepen canonical machine-projection workflows without weakening traceability

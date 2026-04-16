# GEMINI.md - SEAM Continuity Guide

This file is the Gemini-facing resume guide for the SEAM repo.
It points back to the durable project memory rather than replacing it.

## Read Order

1. `PROJECT_STATUS.md`
2. `REPO_LEDGER.md`
3. `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md`
4. `benchmarks/README.md`

## What SEAM Is

SEAM is a machine-first local memory runtime for AI agents.

Core stance:

- canonical truth lives in SQLite
- retrieval and vector layers are derived
- machine-language views are derived artifacts, not replacements for canonical records
- the CLI and dashboard are glassboxes for inspection, debugging, and benchmark proof

## Current Hot Paths

- `seam compile-nl ... --persist`
- `seam context ... --view prompt|evidence|summary|records`
- `seam benchmark run ...`
- `seam benchmark verify ...`
- `seam demo lossless ...`

## Benchmark Reminder

Six benchmark families exist now:

- `lossless`
- `retrieval`
- `embedding`
- `long_context`
- `persistence`
- `agent_tasks`

Published claims should carry bundle hashes, case hashes, fixture hashes, tokenizer info, and git SHA.

## Next Useful Work

- evaluate natural, machine, and hybrid retrieval projections
- strengthen Linux installer verification
- keep benchmark policy and durable memory docs aligned

# ANTIGRAVITY.md - SEAM Continuity Guide

This file is the Antigravity-facing resume guide for the SEAM repo.
Use it as a quick orientation layer, not as the canonical ledger.

## Read First

1. `PROJECT_STATUS.md`
2. `REPO_LEDGER.md`
3. `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md` for benchmark architecture and rollout policy

## Architecture Summary

- SEAM is agent-first and machine-first
- SQLite is the source of truth
- vectors, Chroma, packs, machine artifacts, and benchmark bundles are derived layers
- the benchmark engine is the proof surface for token savings, exactness, and retrieval quality

## Working Commands

```text
seam doctor
seam benchmark run all --persist --output seam-benchmark-report.json
seam benchmark show latest
seam benchmark verify seam-benchmark-report.json
seam dashboard
```

## Non-Negotiables

- lossless means exact reconstruction only
- do not move canonical truth out of SQLite
- do not merge deeper machine-projection behavior without benchmark evidence
- keep continuity docs thin and defer to the durable repo memory files

## Next Useful Work

- benchmark machine-efficient retrieval projections against current defaults
- verify Linux install behavior on a real machine
- continue productizing the operator glassbox only after the benchmark and persistence surfaces stay solid

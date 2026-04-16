# SEAM Benchmarks

This directory is the glassbox benchmark surface for SEAM.

It is designed to make benchmark claims inspectable, reproducible, and contributor-friendly. The benchmark engine records raw traces, case hashes, bundle hashes, fixture hashes, machine-artifact metadata, and improvement-loop actions so published numbers can be audited instead of treated as screenshots.

## Benchmark Families

- `lossless`: exact roundtrip, token savings, byte savings, fluctuation logs, and reversible machine-language search behavior
- `retrieval`: hit rate, recall, MRR, nDCG, exact-pack reversibility, and context traceability
- `embedding`: top-1 correctness and semantic separation margins over the retrieval gold fixtures
- `long_context`: anchor recall and prompt/summary survival over longer synthetic histories
- `persistence`: restart durability for records, machine artifacts, benchmark bundles, and projection indexes
- `agent_tasks`: end-to-end context views and prompt compression behavior for agent-facing workflows

## Public Fixtures

Public fixture files live under `benchmarks/fixtures/`.

Current fixture groups:

- `lossless_cases.json`
- `long_context_cases.json`
- `agent_tasks.json`
- `docs/retrieval_gold_fixtures.json`

Keep fixtures deterministic and easy to understand from raw text.

## CLI

Run the full suite:

```powershell
seam benchmark run all --persist --output seam-benchmark-report.json
```

Run one family:

```powershell
seam benchmark run retrieval
seam benchmark run lossless --tokenizer cl100k_base --include-machine-text
```

Inspect the latest persisted run:

```powershell
seam benchmark show latest
```

Verify a saved bundle:

```powershell
seam benchmark verify seam-benchmark-report.json
```

## Blueprint

The phase rollout, success metrics, publication rules, and contribution plan live in:

- `benchmarks/SEAM_BENCHMARK_BLUEPRINT_V1.md`

## Publishing Rules

When sharing benchmark results, include:

- the saved JSON bundle
- the bundle hash reported by SEAM
- the per-case hashes in the bundle
- the fixture hashes in the manifest
- the commit SHA in the manifest
- the tokenizer used for token accounting
- any optional dependency state that changes measurement depth
- the exact command used to produce the run

## Contribution Guidance

Preferred contribution pattern:

1. add or refine a fixture
2. run the relevant suite
3. inspect the raw case trace
4. propose rule or architecture changes only if the trace shows a real win
5. update the ledger and blueprint if the benchmark policy changes

A later private holdout set can sit beside this public glassbox layer, but this directory is intentionally public and inspectable.

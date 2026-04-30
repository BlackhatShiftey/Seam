# SEAM Benchmarks

This directory is the glassbox benchmark surface for SEAM.

It is designed to make benchmark claims inspectable, reproducible, and contributor-friendly. The benchmark engine records raw traces, case hashes, bundle hashes, fixture hashes, machine-artifact metadata, and improvement-loop actions so published numbers can be audited instead of treated as screenshots.

## Benchmark Families

- `lossless`: exact roundtrip, token savings, byte savings, fluctuation logs, and reversible machine-language search behavior
- `surface`: `SEAM-HS/1` PNG surface exactness, payload hash verification, and direct embedded MIRL/RC query behavior
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

Holdout fixtures live under `benchmarks/fixtures/holdout/` and are ignored by
git. They are publish-only. Do not run them while tuning a change; use them only
to audit a benchmark claim after development is complete.

## CLI

Run the full suite:

```powershell
seam benchmark run all --persist --output seam-benchmark-report.json
```

Run one family:

```powershell
seam benchmark run retrieval
seam benchmark run lossless --tokenizer cl100k_base --include-machine-text
seam benchmark run surface
```

Inspect the latest persisted run:

```powershell
seam benchmark show latest
```

Verify a saved bundle:

```powershell
seam benchmark verify seam-benchmark-report.json
```

Compare two saved bundles or persisted run ids:

```powershell
seam benchmark diff run-a.json run-b.json
seam benchmark diff bench:old bench:new --format json
```

Run publish-only holdout fixtures:

```powershell
seam benchmark run all --holdout --confirm-holdout
```

When no `--output` is supplied, holdout bundles are written under
`benchmarks/runs/holdout/`, separate from routine benchmark outputs.

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

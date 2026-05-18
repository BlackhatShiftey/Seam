# External benchmarks

## What this directory is for

Each subdirectory under `benchmarks/external/<benchmark>/` holds an adapter that
wires an external benchmark into the SEAM evaluation harness. Adapters are
registered through `benchmarks/registry/memory_benchmarks.json`. Each adapter
declares its own `command_env` so the harness knows which environment variable
to set before invocation.

## How to wire a benchmark

1. Set the environment variable the adapter expects.
2. Run `seam bench external --plan` to confirm the harness detects the
   benchmark and can produce an execution plan.
3. Run `seam bench external --scope <id>` to execute the benchmark.

The `--plan` step is always safe (no side effects) and lets you validate wiring
before any work runs.

## LoCoMo quickstart

```bash
seam bench external --quickstart locomo
```

Runs a bundled 10-case synthetic fixture against the SEAM adapter using
string-match scoring (EM, token F1, context recall). Completes in under
60 seconds with no network access and no dataset download required.

The full LoCoMo dataset (`snap-research/locomo` on HuggingFace) can be run
with:

```bash
seam bench external locomo --dataset /path/to/locomo.json
```

## Where adapters go

## Judges

- Default: string-match only (no API key or extra deps needed)
- `--judge stub`: deterministic test judge, always returns correct
- `--judge claude`: requires `pip install seam[bench-judge]` and `ANTHROPIC_API_KEY`
- `--judge openai`: requires `pip install seam[bench-judge]` and `OPENAI_API_KEY`
- Cost: one LLM call per case. Quickstart has ~10 cases.

## Where adapters go

One subdirectory per benchmark. The LoCoMo adapter lives under
`benchmarks/external/locomo/`. Future adapters follow the same pattern
with shared infrastructure under `benchmarks/external/common/`.

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

## Where adapters go

One subdirectory per benchmark. The first adapter will land in SOP 1.

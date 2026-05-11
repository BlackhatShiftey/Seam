# External Memory Benchmark Roadmap

**Status:** Active roadmap track.

This track makes external memory benchmarks a release gate for SEAM memory claims. The registry lives at `benchmarks/registry/memory_benchmarks.json`. The runner lives at `seam_runtime/external_memory_benchmarks.py`. The operator entrypoint is `tools/run_external_memory_benchmarks.py`.

## Required benchmarks

Required benchmarks are LoCoMo, ConvoMem, MemBench, LongMemEval, BEAM / Beyond a Million Tokens, PerLTQA, EverMemBench, Memora, and Mem2ActBench. These are release-blocking for broad long-term memory claims. Until a benchmark has a configured runner command, CI reports it as `NOT_CONFIGURED` / `ACTION_REQUIRED` rather than silently ignoring it.

## Required comparators

Required comparator systems are Mem0, Zep / Graphiti, Letta / MemGPT, MemPalace, Hindsight, and MemMachine. Comparator coverage is tracked in the registry so reporting cannot reduce the competitive field to whichever systems are easiest to beat.

## Optional expansion benchmarks

Optional P3 coverage includes Mem-Gallery, ES-MemEval, MemGUI-Bench, LoCoMo-Plus, MemGround, EngramaBench, DMR, and AMB. Promote any optional benchmark to required when SEAM makes a matching public claim, such as multimodal memory, GUI-agent memory, graph-memory superiority, or production scorecard performance.

## Runner contract

Each external benchmark declares a `command_env`. For example, `locomo` uses `SEAM_BENCH_LOCOMO_COMMAND`. The command must run the benchmark adapter and return exit code `0` on pass. The runner captures command metadata, status, return code, and stdout/stderr tails into a JSON report.

```bash
python tools/run_external_memory_benchmarks.py --plan --scope required
python tools/run_external_memory_benchmarks.py --scope required --output external-memory-benchmark-report.json
python tools/run_external_memory_benchmarks.py --scope required --strict --output external-memory-benchmark-report.json
```

## Gate

A release candidate can only make broad external memory claims when the registry validates, every required benchmark has a configured runner, every configured required benchmark exits successfully, comparator results are present or explicitly marked unavailable with rationale, and the normal SEAM glassbox gate still passes with `seam benchmark gate`.

## Implementation phases

Phase 1 adds the registry, validation logic, runner plan, command execution harness, tests, and CI artifact upload. Phase 2 adds adapters under `benchmarks/external/` for each required benchmark. Phase 3 adds comparator runners. Phase 4 promotes `--strict` into release CI once required adapters and runner commands are available.

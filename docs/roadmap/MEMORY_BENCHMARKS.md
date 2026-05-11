# External Memory Benchmark Roadmap

**Status:** Active roadmap track.

This track makes external memory benchmarks a release gate for SEAM memory claims. The registry lives at `benchmarks/registry/memory_benchmarks.json`. The runner lives at `seam_runtime/external_memory_benchmarks.py`. The operator entrypoint is `tools/run_external_memory_benchmarks.py`.

## Required benchmarks

Required benchmarks are LoCoMo, ConvoMem, MemBench, LongMemEval, BEAM / Beyond a Million Tokens, PerLTQA, EverMemBench, Memora, and Mem2ActBench. These are release-blocking for broad long-term memory claims. Until a benchmark has a configured runner command, CI reports it as `NOT_CONFIGURED` / `ACTION_REQUIRED` rather than silently ignoring it.

## Required comparators

Required comparator systems are Mem0, Zep / Graphiti, Letta / MemGPT, MemPalace, Hindsight, and MemMachine. Comparator coverage is tracked in the registry so reporting cannot reduce the competitive field to whichever systems are easiest to beat.

## Optional expansion benchmarks

Optional P3 coverage includes Mem-Gallery, ES-MemEval, MemGUI-Bench, LoCoMo-Plus, MemGround, EngramaBench, DMR, and AMB. Promote any optional benchmark to required when SEAM makes a matching public claim, such as multimodal memory, GUI-agent memory, graph-memory superiority, or production scorecard performance.

## Prompt serialization and token budget optimization

SEAM should evaluate TOON-style token-oriented serialization as a derived prompt transport format for structured JSON-like payloads. Canonical storage remains MIRL, JSON, and SQLite. Derived prompt payloads may use compact JSON, TOON, SEAM-RC/1, SEAM-LX/1, markdown tables, or another measured codec when that codec is reversible and cheaper under the active tokenizer.

Initial targets are PACK payloads, retrieval result lists, benchmark case matrices, benchmark reports, memory search index outputs, citation/evidence tables, tool result arrays, and comparator scorecards.

Gate:

- codec roundtrip exactness is 100% when the payload requires lossless transport
- canonical JSON/MIRL hashes remain unchanged
- TOON or any alternate codec must beat compact JSON on measured token count before auto-selection
- signed, tamper-evident, or canonical benchmark bundles keep byte-stable canonical JSON unless a formally specified canonical TOON profile is added and tested

Proposed commands:

```bash
seam codec benchmark payload.json
seam codec encode payload.json --format toon
seam codec encode payload.json --format auto
```

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

Phase 1 adds the registry, validation logic, runner plan, command execution harness, tests, and CI artifact upload. Phase 2 adds adapters under `benchmarks/external/` for each required benchmark. Phase 3 adds comparator runners. Phase 4 promotes `--strict` into release CI once required adapters and runner commands are available. Phase 5 adds a prompt codec benchmark layer that compares compact JSON, TOON, SEAM-RC/1, SEAM-LX/1, and markdown-table encodings under the active tokenizer and auto-selects only reversible, lower-token formats.

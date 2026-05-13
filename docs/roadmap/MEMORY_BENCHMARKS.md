# SEAM External Memory Benchmark Roadmap

**Status:** Planned major track. Concept harvested from `bench/add-memory-benchmark-registry`.
**Track:** I — External Memory Benchmarks (Comparator Gate).
**Operator goal:** A new user can `pip install seam`, run one command, and get a comparable LoCoMo score against named systems in under 60 seconds on a clean machine.

## Why this matters

SEAM makes claims about long-term memory, retrieval quality, and context efficiency. Those claims are only credible if SEAM is measured on the same external benchmarks the rest of the agent-memory field uses, and against the same comparator systems readers will compare it to.

This track makes external memory benchmarks a release gate for SEAM memory claims, and makes "install SEAM and run a benchmark" a first-class onboarding path — not a research project the operator has to assemble.

## Required benchmarks

The following benchmarks are release-blocking for broad long-term-memory claims. Each one ships with a configured runner command or CI reports it as `NOT_CONFIGURED` / `ACTION_REQUIRED` — never silently ignored.

- LoCoMo
- ConvoMem
- MemBench
- LongMemEval
- BEAM (Beyond a Million Tokens)
- PerLTQA
- EverMemBench
- Memora
- Mem2ActBench

## Required comparators

Comparator systems are tracked in the registry so reporting cannot reduce the competitive field to whichever systems are easiest to beat. Required comparators:

- Mem0
- Zep / Graphiti
- Letta / MemGPT
- MemPalace
- Hindsight
- MemMachine

## Optional expansion benchmarks

P3 coverage: Mem-Gallery, ES-MemEval, MemGUI-Bench, LoCoMo-Plus, MemGround, EngramaBench, DMR, AMB. Promote any optional benchmark to required when SEAM makes a matching public claim (multimodal memory, GUI-agent memory, graph-memory superiority, production scorecard performance).

## Runner contract

Each registered benchmark declares a `command_env`. For example, `locomo` uses `SEAM_BENCH_LOCOMO_COMMAND`. The command must run the benchmark adapter and return exit code `0` on pass. The runner captures command metadata, status, return code, and stdout/stderr tails into a JSON report.

```bash
seam bench external --plan --scope required
seam bench external --scope required --output external-memory-benchmark-report.json
seam bench external --scope required --strict --output external-memory-benchmark-report.json
```

(The implementation branch uses `tools/run_external_memory_benchmarks.py`. The `seam bench external` CLI alias lands in Phase 2.)

## 60-second install-and-run gate

This is what makes the track plug-and-play. A new user must be able to do all of the following on a clean Linux/WSL machine in under one minute, end to end, with no editing of files:

1. Install SEAM (private repo install, then later `pip install seam`).
2. Run one command to pull a default benchmark adapter (LoCoMo) and a default fixture.
3. Get a JSON report with score, comparator deltas, and an integrity hash.

Proposed UX:

```bash
pip install seam[bench]
seam bench external --quickstart locomo
```

`--quickstart` is allowed to bundle a small public-fixture subset and a default adapter so first-run does not require the user to source datasets, configure env vars, or wire adapters. Full corpora and comparators remain opt-in.

The 60-second gate is measured on the SEAM CI runner with a cold cache. Any change that pushes first-run past 90 seconds is a release blocker for this track.

## Registry

Canonical registry: `benchmarks/registry/memory_benchmarks.json`. The registry is the source of truth for benchmark names, scopes (`required`, `optional`), comparator coverage, command env vars, and dataset sourcing notes.

The registry must validate (schema check + comparator coverage check) before any release that makes a memory claim.

## Gate

A release candidate can only make broad external memory claims when:

- The registry validates.
- Every required benchmark has a configured runner.
- Every configured required benchmark exits successfully under `--strict`.
- Comparator results are present, or explicitly marked unavailable with a recorded rationale.
- The normal SEAM glassbox gate still passes with `seam benchmark gate`.

## Relationship to existing tracks

- Track C (Benchmark Hardening, on main) covers SEAM's *internal* `surface_exact_rate` gate and holdout discipline. Track I sits on top of Track C and adds *external* comparator credibility.
- Track K (Trust, Security, Auditability) supplies the integrity primitives — Benchmark Integrity Levels (BIL-0 through BIL-6) are defined there; this track consumes them by sealing external benchmark bundles at the highest available level.
- Track H (Agent / Skills Compiler) is independent. Skill-quality benchmarks (H3) live there.

## Implementation phases

| Phase | Title | Lands |
|-------|-------|-------|
| 1 | Registry + validation + runner plan + command harness + tests + CI artifact upload | First, on its own PR |
| 2 | `seam bench external` CLI alias + `--quickstart` LoCoMo path | After Phase 1 |
| 3 | Adapters under `benchmarks/external/<benchmark>/` for each required benchmark | One PR per adapter |
| 4 | Comparator runners under `benchmarks/external/comparators/` | One PR per comparator family |
| 5 | Promote `--strict` into release CI once required adapters are stable | Gated promotion |
| 6 | Prompt codec benchmark layer (see `PROMPT_CODEC.md`) compared under the active tokenizer | After codec spec lands |

## Definition of done

Track I is complete when a clean machine can install SEAM, run a default external memory benchmark in under 60 seconds, produce a comparable LoCoMo score against at least three named comparators, and seal the resulting bundle at the highest BIL level Track K currently supports.

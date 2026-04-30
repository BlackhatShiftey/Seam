# SEAM Benchmark Blueprint v1

This document maps the recommended benchmark rollout for SEAM and records what the benchmark system is supposed to prove.

## Objective

Build a glassbox benchmark engine that proves four things at once:

- exactness is preserved
- token-efficiency claims are measurable
- retrieval quality does not regress when machine-efficient views are introduced
- benchmark results are hard to tamper with and easy to audit

## Benchmark Families

SEAM tracks eight benchmark families:

1. `lossless`
2. `readable`
3. `surface`
4. `retrieval`
5. `embedding`
6. `long_context`
7. `persistence`
8. `agent_tasks`

## North-Star Metrics

Track these metrics across releases:

- `lossless_exact_rate`
- `surface_exact_rate`
- `payload_hash_match_rate`
- `token_savings_ratio`
- `retrieval_quality` via Recall@k, MRR, and nDCG
- `traceability`
- `latency`
- `durability`
- `agent_lift`

Release rule:

- no release if lossless exactness drops below 100%
- no release if `SEAM-HS/1` surface extraction or payload hash matching drops
  below 100%

## Phase Rollout

### Phase 1: Benchmark core

Status: implemented

Build the benchmark engine, fixture loading, raw traces, per-case hashes, bundle hashes, persisted run history, and bundle verification.

Deliverables:

- six-family benchmark runner
- `benchmark run`, `benchmark show`, and `benchmark verify`
- auditable JSON bundle output
- benchmark persistence in SQLite

### Phase 2: Canonical machine projections

Status: partially implemented

Promote machine artifacts and projections into first-class derived persistence while keeping canonical truth in SQLite records.

Deliverables:

- `machine_artifacts` persistence
- `projection_index` persistence
- clearer runtime workflows for reading and writing derived machine views

### Phase 3: Retrieval projection evaluation

Status: next

Evaluate `natural`, `machine`, and `hybrid` retrieval projections before pushing machine-language views deeper into retrieval or optional Chroma layers.

Deliverables:

- tokenizer-backed retrieval comparisons
- measured quality deltas across projection styles
- promotion criteria for derived machine projections

### Phase 3A: Holographic Surface evaluation

Status: implemented for v1

Treat `SEAM-HS/1` as a first-class visual surface layer for immutable directly
readable memory snapshots. The benchmark proves that MIRL and `SEAM-RC/1`
payloads survive PNG pixel encoding exactly and remain queryable without OCR,
natural-language recompilation, or SQLite import.

Deliverables:

- `surface` benchmark family
- `surface_exact_rate == 1.0`
- `payload_hash_match_rate == 1.0`
- direct query checks against embedded MIRL and RC/1 payloads
- default coverage for `bw1`, `rgb24`, and explicit `rgba32`

### Phase 4: Improvement loop promotion

Status: in progress

Use benchmark regressions and fluctuation logs to guide reversible rule additions, ranking changes, and projection refinement.

Deliverables:

- stable rule-promotion process
- benchmark-driven regression triage
- explicit improvement-loop actions in benchmark output

### Phase 5: Contributor glassbox and cross-agent continuity

Status: implemented for the public repo surface

Make the benchmark system easy to inspect and extend, and add assistant-specific continuity files so other agents can resume work quickly.

Deliverables:

- public benchmark fixtures and README
- bundle verification and publication policy
- `CLAUDE.md`, `GEMINI.md`, and `ANTIGRAVITY.md` pointing back to the durable project memory

## Publishing Requirements

Every published result should include:

- the benchmark JSON bundle
- bundle hash
- per-case hashes
- fixture hashes
- git SHA
- tokenizer and dependency state
- platform and Python version
- exact CLI command used to generate the run

## Contributor Rules

- keep public fixtures deterministic
- do not claim wins without bundle verification
- prefer benchmark traces over intuition when changing rules
- update `PROJECT_STATUS.md` and `REPO_LEDGER.md` when benchmark policy changes
- keep agent-specific continuity files lightweight and defer to the durable repo memory

## Next Recommended Work

1. Add natural vs machine vs hybrid retrieval projection experiments.
2. Validate the Linux installer on a real machine.
3. Add holdout-suite strategy for leaderboard-style publication.
4. Add benchmark diff/publish helpers once the evaluation surface stabilizes.

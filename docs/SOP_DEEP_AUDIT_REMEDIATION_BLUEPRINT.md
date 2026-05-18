# SEAM Deep Audit Remediation SOP Blueprint

## Purpose

This SOP defines the next SEAM deep-audit remediation cycle after
`HISTORY#197`. It is for future agents debugging and testing SEAM before
benchmark wiring and benchmark execution, and before any future WebUI wiring.

The cycle goal is to convert audit claims into verified fixes, benchmark
readiness, and auditable closeout records without breaking SEAM continuity,
active/archive boundaries, or concurrent agent work.

## Guardrails

1. Start every session by reading, in order:
   - `PROJECT_STATUS.md`
   - `REPO_LEDGER.md`
   - `HISTORY_INDEX.md`
   - `docs/CODE_LAYOUT.md`
   - `docs/DATA_ROUTING.md` when touching history, ledgers, routing,
     maintenance records, context budgets, or auditability.
2. Do not read all of `HISTORY.md`.
3. Load history only through bounded context packs or surgical indexed ranges:
   ```bash
   python -m tools.history.build_context_pack --topics audit verify benchmark --latest 5 --token-budget 1800
   python -m tools.history.build_context_pack --route protocol/context --latest 3 --token-budget 1200
   ```
4. Treat `HISTORY#197` as the current handoff unless a newer validated entry
   exists in `HISTORY_INDEX.md`.
5. Do not expose, copy, summarize, or commit secrets, local `.env` values,
   private tokens, provider session links, chat/share URLs, or transcript URLs.
6. Search and edit only active paths unless the task explicitly says otherwise:
   `seam_runtime/`, `seam.py`, `experimental/`, `tools/`, `scripts/`,
   `installers/`, `docs/`, tests, and root status files.
7. Avoid inactive or generated paths: `archive/code/`, `docs/archive/`,
   `build/`, `.venv/`, `test_seam/`, caches, and generated artifacts.
8. Do not wire `experimental/webui/` in this phase. It is functional and should
   remain a preserved browser dashboard prototype until benchmark readiness is
   complete and the operator explicitly starts WebUI wiring.
9. Do not revert or overwrite concurrent edits. Check file ownership before
   editing and coordinate with other active agents.
10. Runtime code changes require tests. Documentation-only changes still require
    diff review and secret/session-link scan.

## Known Current State

`HISTORY#197` fixed RateLimiter thread safety, SEAM-LX/1 unknown-status
rejection, dashboard lazy import isolation for `experimental.retrieval_orchestrator`,
and benchmark temporary SQLite cleanup. Operator priority is debug/test SEAM,
wire and run benchmarks, then defer WebUI wiring until benchmarks are credible.

## Triage Matrix

| Tier | Scope | Acceptance Criteria |
|---|---|---|
| P0 correctness/security | Data loss, auth/rate-limit bypass, path traversal, unbounded local file access, secret exposure, concurrency corruption, incorrect lossless claims | Repro test fails before fix; fix blocks exploit/regression; focused test passes; full active suite passes; SEAM gates pass; no secrets/session URLs in diff |
| P1 benchmark/readiness | Anything blocking benchmark plans, adapters, quickstarts, bundle/gate/diff, baseline reproducibility, temp artifact cleanup, publication metadata | Repro test or benchmark smoke fails before fix; command exits non-zero before fix and zero after; bundle hash/case hashes emitted where required; gate and diff workflow documented or passing |
| P2 scalability | O(N) search where indexed retrieval is expected, pagination gaps, avoidable memory spikes, multi-worker/process-local limits, large bundle handling | Benchmark or profiling fixture demonstrates current limit; bounded query/page behavior is enforced; regression test covers upper bound or query plan; no broad architectural rewrite |
| P3 architecture cleanup | Dead-code decisions, assertion hygiene, shell guardrail polish, type semantics clarity, docs alignment | Narrow scoped patch; behavior unchanged unless explicitly tested; cleanup has owner, deletion/archive decision, and continuity record |

Promotion rule: if a P2/P3 item can lose data, expose private files, bypass
auth/rate limits, or invalidate benchmark claims, promote it to P0/P1.

## Red-Green Verification Workflow

1. Claim calibration:
   ```bash
   git status --short
   python -m tools.history.build_context_pack --topics audit verify benchmark --latest 5 --token-budget 1800
   rg "<claim keyword>" seam_runtime seam.py experimental tools scripts installers docs test_seam_all tests
   ```
2. Write or identify a failing test before changing runtime behavior.
3. Run the focused failing test and capture the failure:
   ```bash
   python -m pytest test_seam_all/test_seam.py -q -k "<focused expression>"
   ```
4. Implement the smallest fix in the owned active file set.
5. Re-run the focused test until it passes:
   ```bash
   python -m pytest test_seam_all/test_seam.py -q -k "<focused expression>"
   ```
6. Run relevant module compile checks:
   ```bash
   python -m py_compile seam.py
   python -m compileall -q seam_runtime experimental tools scripts installers
   ```
7. Run the active regression suite and SEAM gates:
   ```bash
   python -m pytest test_seam_all/test_seam.py -q
   python -m tools.history.verify_integrity
   python -m tools.history.verify_routing
   python -m tools.history.verify_continuity
   python -m tools.streams.verify_streams
   ```
8. Review the diff before staging:
   ```bash
   git diff --check
   git diff --stat
   git diff -- <owned paths>
   ```
9. Scan the diff for secret/session-link patterns:
    ```bash
    git diff -- . ':!docs/archive' ':!archive/code' \
      | rg -n "sk-[A-Za-z0-9_-]+|ghp_[A-Za-z0-9_]+|BEGIN (RSA |OPENSSH |EC |)PRIVATE KEY|session|share\\.openai|chatgpt\\.com/share|claude\\.ai/share|gemini\\.google\\.com/share" || true
    ```

## Benchmark Workflow

1. Inspect the external benchmark plan without running heavy workloads:
   ```bash
   seam bench external --plan
   ```
2. Verify the LoCoMo quickstart path first:
   ```bash
   seam bench external --quickstart locomo --adapter seam --judge stub
   ```
3. Only then run optional comparator quickstarts when extras and credentials are
   intentionally configured by the operator:
   ```bash
   seam bench external --quickstart locomo --adapter mem0 --judge stub
   seam bench external --quickstart locomo --adapter zep --judge stub
   ```
4. Use built-in benchmark families for runtime regressions before external
   publication claims:
   ```bash
   seam benchmark run retrieval --format json
   seam benchmark run readable --format json
   seam benchmark run surface --format json
   seam benchmark run long_context --format json
   ```
5. Verify each bundle before trusting it:
   ```bash
   seam benchmark gate <bundle>
   seam benchmark diff <baseline-bundle> <candidate-bundle>
   ```
6. Publication-grade claims must include command, git SHA, bundle hash,
   per-case hashes, fixture hashes, tokenizer/dependency state, diff output,
   gate output, and any required holdout bundle.
7. Holdout runs are publish-time only:
   ```bash
   seam benchmark run all --holdout --confirm-holdout
   ```
8. Store publication-grade benchmark results outside the repo through the
   operator archival script:
   ```powershell
   scripts/store_benchmark.ps1 -Bundle <bundle-path> -Label <short-label>
   ```
9. Do not commit generated benchmark result bundles unless they are deliberately
   promoted as repo-owned fixtures or docs assets.

## Delegation Protocol

1. Split work by file ownership before editing. Each agent owns a disjoint file
   set and announces it in the handoff or chat.
2. Separate runtime fixes, tests, benchmark execution, and
   documentation/continuity when practical.
3. Never edit a file touched by another active agent without reading
   `git diff -- <file>` and confirming the intended merge.
4. Before changing a file:
   ```bash
   git status --short
   git diff -- <file>
   ```
5. Handoff format:
   - Owned files:
   - Claim/tier:
   - Failing test command:
   - Passing focused command:
   - Full suite command:
   - SEAM gates:
   - Benchmark commands, if any:
   - Known gaps:
6. Verification handoff must name exact commands and whether they passed,
   failed, or were skipped with reason.
7. Documentation-only workers must not modify runtime code, tests, history,
   snapshots, generated files, or cache paths unless explicitly delegated.

## Concrete Backlog

| Item | Tier | Owner Area | Acceptance Criteria |
|---|---:|---|---|
| Vector search O(N) | P2 | `seam_runtime/` retrieval/vector paths | Indexed or bounded retrieval path is used for expected vector search; test or benchmark proves no full scan for scalable path |
| `load_ir` pagination | P2 | runtime persistence/query path | Caller can request bounded pages; tests cover first, middle, empty, and invalid page semantics |
| CLI/dashboard local file path boundaries | P0 | CLI, dashboard, file ingest | Local path inputs reject traversal/out-of-scope reads where applicable; tests cover allowed and blocked paths |
| REST/MCP rate-limit scope | P0 | REST/MCP surfaces | Process-local limit semantics are explicit; multi-worker unsafe modes are refused or externally gated; tests cover scope boundaries |
| SQLite connection/concurrency strategy | P0 | storage/runtime | Concurrent operations avoid shared-connection corruption; tests cover threaded access and cleanup |
| Exact-pack timestamp semantics | P1 | pack/context tooling | Timestamp source and ordering semantics are deterministic and documented; tests cover ties and missing timestamps |
| MIRL parse error context | P3 | MIRL parser/CLI reports | Parse failures include bounded line/column/context without leaking full private input |
| LX1 float/int type preservation | P1 | SEAM-LX/1 codec | Roundtrip preserves numeric type where the format claims exactness; tests cover int, float, and edge numeric values |
| Snapshot budget clarity | P3 | history/snapshot tooling docs | Snapshot token/size budget behavior is explicit; no full-history read required to understand it |
| Dashboard shell guardrails | P0 | dashboard shell/command palette | Shell commands are bounded/disabled as policy requires; tests or smoke checks cover blocked dangerous input |
| `assertTrue` cleanup | P3 | tests | Replace remaining ambiguous `assertTrue` assertions with specific assertions in touched test areas; no broad churn without owner |
| Experimental dead-code decision | P3 | `experimental/` docs/code | Decide keep/archive/delete per active import evidence; no archive resurrection; tests prove retained imports still work |
| Benchmark baseline expansion | P1 | benchmark registry/runs | Baselines cover retrieval, compression, surface, LoCoMo quickstart, and diff/gate expectations with reproducible metadata |

## Final Closeout Checklist

Run this checklist after material runtime/test/benchmark changes:

1. Review, focused tests, full suite, and compile checks:
   ```bash
   git status --short
   git diff --check
   git diff --stat
   python -m pytest test_seam_all/test_seam.py -q -k "<focused expression>"
   python -m pytest test_seam_all/test_seam.py -q
   python -m py_compile seam.py
   python -m compileall -q seam_runtime experimental tools scripts installers
   ```
2. Benchmark smoke or gate when benchmark behavior changed:
   ```bash
   seam bench external --plan --scope all
   seam bench external --quickstart locomo --adapter seam --judge stub
   seam benchmark gate <bundle>
   seam benchmark diff <baseline-bundle> <candidate-bundle>
   ```
3. Secret/session-link scan of candidate diff:
   ```bash
   git diff -- . ':!docs/archive' ':!archive/code' \
     | rg -n "sk-[A-Za-z0-9_-]+|ghp_[A-Za-z0-9_]+|BEGIN (RSA |OPENSSH |EC |)PRIVATE KEY|session|share\\.openai|chatgpt\\.com/share|claude\\.ai/share|gemini\\.google\\.com/share" || true
   ```
4. Append one `HISTORY.md` entry with changed files, commands, failures,
   skipped checks, benchmark outputs, and unresolved follow-ups.
5. Rebuild `HISTORY_INDEX.md` and write one snapshot JSON:
   ```bash
   python -m tools.history.rebuild_index
   python -m tools.history.write_snapshot --agent <agent-name> --entries <latest-entry-id> --token-budget 1800
   ```
6. Run SEAM gates:
   ```bash
   python -m tools.history.verify_integrity
   python -m tools.history.verify_routing
   python -m tools.history.verify_continuity
   python -m tools.streams.verify_streams
   ```
7. If `ROADMAP.md` changed, refresh roadmap stream and cross-index:
   ```bash
   python -m tools.streams.roadmap_parser
   python -m tools.streams.rebuild_cross_index
   ```
8. If stream files changed, rebuild the cross-index:
   ```bash
   python -m tools.streams.rebuild_cross_index
   ```

Closeout is not complete until command results are recorded with exact pass,
fail, or skipped status. Do not claim benchmark improvement without a bundle
gate and a diff against a named baseline.

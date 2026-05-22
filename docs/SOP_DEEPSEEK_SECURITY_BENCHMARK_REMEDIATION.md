# SOP: DeepSeek Security and Benchmark Remediation

Use this handoff when asking DeepSeek to continue the security/benchmark hardening pass that started from the 23 findings reported on 2026-05-21.

## Current Stopping Point

Codex completed and regression-tested a first remediation slice:

- Benchmark runner truthfulness:
  - context-only retrieval no longer earns answer EM/F1 credit
  - cross-judge receives the real question, gold answer, and prediction
  - `StubJudge` abstains instead of marking every answer correct
  - provider judge request/parse failures raise into per-case runner errors instead of silently becoming incorrect verdicts
- BIL sealing:
  - external result manifests preserve benchmark/adapter/dataset/judge metadata across future result versions
  - unjudged external results cannot be sealed above BIL-0 unless explicitly overridden
- REST/API and hooks:
  - `/benchmark` maps `ValueError` to HTTP 400
  - pre-commit fails closed when Python is missing
  - pytest config is consolidated into `pytest.ini` and `httpx` is listed for the dashboard extra
- Runtime hardening:
  - in-memory `SQLiteStore` has `close()` and context-manager support
  - history context-pack `--refs` matching is literal, not regex
  - snapshot writes use temp file plus atomic replace
  - holographic surface encode has a configurable payload-size guard
  - Textual dashboard subprocess shell execution is disabled by default and requires `SEAM_DASHBOARD_ALLOW_SHELL=1`
  - WebUI bearer token storage moved from `localStorage` to `sessionStorage` with best-effort cleanup of the legacy key

Focused verification passed:

```bash
.venv/bin/python -m pytest test_seam_all/test_locomo_judge.py test_seam_all/test_locomo_zep_adapter.py test_seam_all/test_benchmark_integrity.py test_seam_all/test_git_hooks.py test_seam_all/test_server_benchmark_endpoint.py test_seam_all/test_storage_lifecycle.py test_seam_all/test_holographic_safety.py tools/history/test_history_tools.py::TestContextPack::test_refs_pattern_is_literal_not_regex tools/history/test_history_tools.py::TestSnapshots::test_write_snapshot_uses_atomic_replace tests/audit/test_openai_judge_gpt5.py test_seam_all/test_seam.py::SeamTests::test_textual_dashboard_bang_runs_shell_commands test_seam_all/test_seam.py::SeamTests::test_textual_dashboard_blocks_shell_subprocess_by_default
```

Result: `57 passed in 258.88s`.

WebUI focused verification passed:

```bash
cd experimental/webui
npm test -- --run src/api/apiClient.test.ts
```

Result: `11 passed`.

Broad verification was intentionally stopped:

```bash
.venv/bin/python -m pytest
```

Stopped with `SIGINT` after `93 passed in 576.13s`. Treat this as incomplete, not passing.

## Do First

1. Read the required repo startup context in `AGENTS.md` order:
   - `PROJECT_STATUS.md`
   - `REPO_LEDGER.md`
   - `HISTORY_INDEX.md`
   - `docs/CODE_LAYOUT.md`
   - `docs/DATA_ROUTING.md`
2. Do not read all of `HISTORY.md`.
3. Run `git status --short --branch`.
4. Preserve existing user changes. At the time of this handoff, `test_seam_all/test_locomo_runner_cli.py` already had an unrelated local edit changing quickstart timeout from 60s to 180s. Do not revert it unless the operator explicitly asks.
5. Re-run the focused verification above before building on the patch.

## Parallel Agent Plan

Use DeepSeek parallel workers. Each worker must have a disjoint write scope and must not revert edits made by other workers.

### Agent A: Benchmark Truth and BIL Integrity

Scope:

- `benchmarks/external/common/`
- `seam_runtime/benchmark_integrity.py`
- benchmark integrity and external benchmark tests

Tasks:

- Review every score field and judge aggregate for truthfulness.
- Confirm stub and unjudged results cannot be confused with real judge evidence.
- Add negative tests for malformed judge payloads, cross-judge errors, and future external result versions.
- Verify BIL-2 manifests contain enough metadata for LoCoMo, LongMemEval, and BEAM outputs.

Do:

- Keep stub output smoke-only.
- Make errors explicit and machine-detectable.
- Preserve deterministic hashes where possible.

Do not:

- Reintroduce context-as-answer scoring.
- Treat provider outages as benchmark model failures.
- Seal unjudged or stub results by default.

### Agent B: Runtime/API/Storage Safety

Scope:

- `seam_runtime/server.py`
- `seam_runtime/runtime.py`
- `seam_runtime/storage.py`
- `seam_runtime/vector_adapters.py`
- API/storage/runtime tests

Tasks:

- Audit REST endpoints for 2xx-on-error behavior.
- Re-check `persist_ir` rollback semantics and concurrent ingestion behavior.
- Assess whether `SQLiteStore.ingest_text` source-ref supersede logic needs a transaction boundary.
- Review PgVector identifier handling and document why the current regex is sufficient or replace it with safer identifier composition.

Do:

- Add focused failing tests first.
- Keep SQLite as canonical truth and vector indexes derived.
- Prefer existing storage helpers.

Do not:

- Hide rollback failures.
- Weaken pgvector table-name validation.
- Add broad storage rewrites unrelated to the finding.

### Agent C: Operator Surface Safety

Scope:

- `seam_runtime/dashboard.py`
- `experimental/webui/`
- CLI/dashboard/webui tests

Tasks:

- Review all TUI command paths for subprocess execution, sensitive output leakage, and unsafe exception text.
- Review WebUI token handling after the `sessionStorage` move.
- Decide whether additional controls are needed, such as token-in-memory only, explicit logout, or CSP guidance.
- Add tests for `SEAM_DASHBOARD_ALLOW_SHELL=1` opt-in behavior and redacted exception display.

Do:

- Keep `pwd` and `cd` built-in behavior separate from subprocess shell execution.
- Keep operator opt-in explicit.
- Avoid exposing bearer tokens in UI errors or logs.

Do not:

- Enable subprocess shell execution by default.
- Store bearer tokens in `localStorage`.
- Add browser auth flows without operator approval.

### Agent D: History/Tooling/Surface Hardening

Scope:

- `tools/history/`
- `tools/git-hooks/`
- `seam_runtime/holographic.py`
- continuity and surface tests

Tasks:

- Complete audit of regex use in history/stream tools.
- Validate atomic writes for all generated continuity artifacts, not only snapshots.
- Review holographic capacity math for `bw1`, especially width * height not divisible by 8.
- Add tests for payload limit env parsing and capacity reporting.

Do:

- Treat history artifacts as audit-critical.
- Use temp file plus `os.replace()` for durable generated files where appropriate.
- Keep `--refs` matching literal unless a separate explicit regex option is designed.

Do not:

- Hand-edit derived indexes.
- Read all `HISTORY.md`.
- Make broad stream-tool changes without continuity verification.

## Final Integration Steps

1. Collect all worker diffs and review for overlap.
2. Run focused tests from each worker.
3. Run WebUI tests if `experimental/webui/` changed:

   ```bash
   cd experimental/webui
   npm test -- --run
   ```

4. Run active Python verification:

   ```bash
   .venv/bin/python -m pytest
   .venv/bin/python -m compileall seam_runtime benchmarks tools scripts installers
   git diff --check
   ```

5. Run SEAM continuity closeout:

   ```bash
   .venv/bin/python -m tools.history.verify_integrity
   .venv/bin/python -m tools.history.verify_routing
   .venv/bin/python -m tools.history.verify_continuity
   .venv/bin/python -m tools.streams.verify_streams
   ```

6. If repo state changed materially, append one `HISTORY.md` entry, rebuild `HISTORY_INDEX.md`, write one snapshot, and rebuild stream/cross-index derived files as required by `AGENTS.md`.

## Final Audit Requirement

After all fixes are integrated and verified, run a fresh full audit of the active codebase to find the next highest-risk problems. The audit must cover:

- benchmark truthfulness and publication claims
- REST/MCP/dashboard/WebUI exposed surfaces
- credential/token/session handling
- shell/subprocess/file-system access
- history, routing, snapshot, and stream integrity
- SQLite/vector consistency and rollback paths
- large-input and memory-exhaustion paths
- dependency/config drift

The final audit report must separate:

- fixed in this pass
- still open from the original 23 findings
- newly discovered high-risk issues
- false positives with evidence
- verification commands and results

Do not call the work complete until the original vulnerable paths and the new audit findings have reproducible tests or explicit proof gaps.

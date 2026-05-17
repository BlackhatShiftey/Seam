# SOP: External Memory Benchmark Registry + Runner + CLI (Phases 1+2)

Handoff target: DeepSeek (or any contributor)
Track: I — External Memory Benchmarks
Canonical spec: `docs/roadmap/MEMORY_BENCHMARKS.md`
Sequence: **SOP 0 of 5.** Prereq for SOP 1 (SEAM LoCoMo adapter), SOP 2 (LLM-judge), SOP 3 (Mem0 comparator), SOP 4 (Zep comparator).
Source material: drafted on remote branch `origin/bench/add-memory-benchmark-registry` and never merged.

## 1. Goal

After this PR, the operator can run:

```bash
seam bench external --plan --scope required
seam bench external --scope required --output report.json
seam bench external --scope required --strict --output report.json
```

and get either a plan of what runners are configured or a JSON report driven by environment variables (one env var per benchmark). LoCoMo, ConvoMem, MemBench, LongMemEval, etc. each have a `command_env` (e.g. `SEAM_BENCH_LOCOMO_COMMAND`). When the env is unset the benchmark reports `NOT_CONFIGURED`. When set the runner shells out and captures the result.

This PR ships **no adapter implementations**. It ships the harness that future adapters plug into.

## 2. Scope

In:
- `benchmarks/registry/memory_benchmarks.json` — registry of required/optional benchmarks and comparators
- `seam_runtime/external_memory_benchmarks.py` — loader, validator, plan, runner, pretty renderers
- `tools/run_external_memory_benchmarks.py` — standalone CLI for the runner
- `seam_runtime/cli.py` — `seam bench external` subcommand wiring
- Tests under `test_seam_all/test_external_memory_benchmarks.py`
- `benchmarks/external/README.md` — operator-facing how-to
- HISTORY entry + PROJECT_STATUS update

Out:
- Any actual benchmark adapter (LoCoMo, Mem0, etc.) — those are SOPs 1, 3, 4
- LLM-judge scoring — SOP 2
- `--quickstart locomo` shorthand — SOP 1 wires this when the LoCoMo adapter lands

## 3. Prerequisites

- Read `docs/roadmap/MEMORY_BENCHMARKS.md`
- Read the existing draft on `origin/bench/add-memory-benchmark-registry` for the registry JSON and `seam_runtime/external_memory_benchmarks.py` module. Most of this PR is reconciling those files onto `main` with minor adjustments.

Do not merge the whole branch. It contains unrelated divergent changes (removed history, removed docs). Cherry-pick or copy only the four files named above.

## 4. Files to create or modify

### 4.1 `benchmarks/registry/memory_benchmarks.json`

Copy verbatim from `origin/bench/add-memory-benchmark-registry`. Required fields per benchmark: `id`, `name`, `priority`, `required`, `command_env`. Required fields per comparator: `id`, `name`, `required`. The registry must include the policy block:

```json
"policy": {
  "strict_mode_failure_statuses": ["FAIL", "NOT_CONFIGURED"]
}
```

Add it if missing on the source branch.

### 4.2 `seam_runtime/external_memory_benchmarks.py`

Copy verbatim from `origin/bench/add-memory-benchmark-registry` with these adjustments:

1. **REGISTRY_PATH** must resolve from the package directory, not from a hardcoded user path. Pattern already correct on the source branch:
   ```python
   REGISTRY_PATH = Path(__file__).resolve().parent.parent / "benchmarks" / "registry" / "memory_benchmarks.json"
   ```
2. Public surface that **must not change**: `load_memory_benchmark_registry`, `validate_memory_benchmark_registry`, `benchmark_plan`, `run_external_memory_benchmarks`, `render_external_memory_plan_pretty`, `render_external_memory_report_pretty`, `PLAN_VERSION`, `REPORT_VERSION`. SOPs 1-4 import these names.
3. `run_external_memory_benchmarks` already truncates stdout/stderr to 4000 chars in `_case_result`. Keep that behavior — adapter output can be large.

### 4.3 `tools/run_external_memory_benchmarks.py`

Copy verbatim from `origin/bench/add-memory-benchmark-registry`. It is a thin argparse wrapper around the module.

### 4.4 `seam_runtime/cli.py`

Add a new subcommand under the existing parser tree:

```python
bench_parser = subparsers.add_parser("bench", help="External memory benchmark registry and runner")
bench_subparsers = bench_parser.add_subparsers(dest="bench_command", required=True)
bench_external_parser = bench_subparsers.add_parser(
    "external",
    help="Run or plan external memory benchmarks (LoCoMo, MemBench, etc.)",
)
bench_external_parser.add_argument("--scope", default="required",
    help="required, all, or a single benchmark id")
bench_external_parser.add_argument("--plan", action="store_true",
    help="Print the configured/missing runner plan and exit 0")
bench_external_parser.add_argument("--strict", action="store_true",
    help="Fail when required runners are NOT_CONFIGURED")
bench_external_parser.add_argument("--output", help="Write JSON to this path")
bench_external_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")
bench_external_parser.add_argument("--timeout-seconds", type=int, default=3600)
bench_external_parser.add_argument("--quickstart", help="Reserved for SOP 1 (LoCoMo). Accept but error with a clear message if used here.")
```

In the dispatcher, route `args.command == "bench" and args.bench_command == "external"` to a new helper that mirrors `tools/run_external_memory_benchmarks.py:main`. Reuse the same renderers; do not reimplement them.

`--quickstart` is **reserved**. If passed in this PR, print:
```
--quickstart requires a benchmark adapter. See docs/SOP_EXTERNAL_BENCH_LOCOMO_SEAM_ADAPTER.md (SOP 1).
```
and exit 2.

### 4.5 `benchmarks/external/README.md`

New file. Three sections only:

1. **What this directory is for.** Adapters under `benchmarks/external/<benchmark>/` are registered through `benchmarks/registry/memory_benchmarks.json`. Each adapter sets its own `command_env`.
2. **How to wire a benchmark.** Set the env var, run `seam bench external --plan` to confirm, then `seam bench external --scope <id>` to execute.
3. **Where adapters go.** One subdirectory per benchmark. First adapter lands in SOP 1.

Keep it under 80 lines. No promises about LoCoMo until SOP 1 lands.

### 4.6 `test_seam_all/test_external_memory_benchmarks.py`

New file. Cover:

- registry loads and validates
- duplicate benchmark id raises `ValueError`
- missing `command_env` raises `ValueError`
- `benchmark_plan(scope="required")` returns only required benchmarks
- `benchmark_plan(scope="all")` returns all benchmarks
- `benchmark_plan(scope="unknown_id")` raises `ValueError`
- `run_external_memory_benchmarks` with no env vars returns status `ACTION_REQUIRED` and every case `NOT_CONFIGURED`
- `run_external_memory_benchmarks` with a stub env var pointing at `python -c "import sys; sys.exit(0)"` returns status `PASS` for that case
- `run_external_memory_benchmarks(strict=True)` with unconfigured required runners returns status `FAIL`
- pretty renderers return non-empty strings for both plan and report
- CLI smoke: `subprocess.run(["python", "-m", "tools.run_external_memory_benchmarks", "--plan"])` exits 0 and produces JSON when `--format json` is passed

Use `monkeypatch.setenv` and `monkeypatch.delenv` to isolate env state. Do not leak env between tests.

### 4.7 `.github/workflows/ci.yml`

Add one job step that runs `python -m tools.run_external_memory_benchmarks --plan --format json --output external-memory-benchmark-plan.json` and uploads the artifact. No `--strict`. The plan is informational on this PR. Strict mode goes in SOP 5 (deferred).

## 5. DeepSeek implementation checklist

Work through these in order. Tick each box in the PR description as you complete it.

- [ ] Copied `benchmarks/registry/memory_benchmarks.json` from `origin/bench/add-memory-benchmark-registry`; added `policy` block if missing
- [ ] Copied `seam_runtime/external_memory_benchmarks.py`; confirmed `REGISTRY_PATH` resolves correctly from a packaged install (`python -c "from seam_runtime.external_memory_benchmarks import load_memory_benchmark_registry; load_memory_benchmark_registry()"` succeeds)
- [ ] Copied `tools/run_external_memory_benchmarks.py`; `python -m tools.run_external_memory_benchmarks --plan` runs
- [ ] Added `seam bench external` subcommand to `seam_runtime/cli.py` per section 4.4
- [ ] `--quickstart` reserved-flag path prints the SOP 1 pointer and exits 2
- [ ] Created `benchmarks/external/README.md` per section 4.5
- [ ] Wrote `test_seam_all/test_external_memory_benchmarks.py` covering all bullets in section 4.6
- [ ] All new tests pass locally (`pytest test_seam_all/test_external_memory_benchmarks.py -v`)
- [ ] Full test suite still passes (`pytest test_seam_all -x`)
- [ ] Added CI step in `.github/workflows/ci.yml` per section 4.7; uploaded artifact named `external-memory-benchmark-plan.json`
- [ ] Updated `PROJECT_STATUS.md`: add bullet under "What Is Stable" mentioning `seam bench external --plan` and the registry path
- [ ] Appended HISTORY entry per template in section 8
- [ ] Ran `python -m tools.history.verify_continuity` and it passes
- [ ] Ran `python -m tools.history.verify_integrity` and it passes
- [ ] Pushed branch and opened **draft** PR titled `Phase 1+2: External memory benchmark registry + seam bench external`

## 6. Reviewer verification checklist

Reviewer runs each command and ticks the box.

- [ ] `git log --oneline | head -5` shows one focused commit (or a tight series)
- [ ] `python -m tools.run_external_memory_benchmarks --plan --format json` produces JSON with `version: SEAM-EXTERNAL-MEMORY-BENCHMARK-PLAN/1`
- [ ] `python -m tools.run_external_memory_benchmarks --plan --format pretty` produces a human-readable plan listing all required benchmarks as `missing`
- [ ] `seam bench external --plan --format json` produces the same output as the standalone tool
- [ ] `SEAM_BENCH_LOCOMO_COMMAND='python -c "print(0)"' python -m tools.run_external_memory_benchmarks --scope locomo --format json` shows status `PASS` for the LoCoMo case
- [ ] `python -m tools.run_external_memory_benchmarks --strict` exits non-zero when no env vars are set
- [ ] `pytest test_seam_all/test_external_memory_benchmarks.py -v` passes (10+ tests)
- [ ] `pytest test_seam_all -x` passes (full suite)
- [ ] `python -m tools.history.verify_continuity` passes
- [ ] `python -m tools.history.verify_integrity` passes
- [ ] `seam doctor` still returns PASS
- [ ] Grep for secret-shaped strings returns nothing: `grep -RE "(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|claude\.ai/(chat|share))" benchmarks/ seam_runtime/external_memory_benchmarks.py tools/run_external_memory_benchmarks.py`
- [ ] `benchmarks/external/README.md` is under 80 lines and makes no promises about LoCoMo
- [ ] No changes to `seam_runtime/storage.py`, `seam_runtime/nl.py`, `seam_runtime/search.py`, `seam_runtime/pack.py`, `seam_runtime/mcp.py`, `seam_runtime/server.py`, or `seam.py` core dispatch beyond the `bench` subcommand wiring
- [ ] No new third-party dependency added to `requirements.txt` or `pyproject.toml`

## 7. Acceptance commands (single block — copy and run)

```bash
# Install from PR branch
pip install -e .

# Plan output (every required benchmark should appear as missing)
seam bench external --plan --format pretty

# JSON plan
seam bench external --plan --format json --output /tmp/plan.json
jq '.version, .summary.missing_required_commands' /tmp/plan.json

# Stub run for a single benchmark
SEAM_BENCH_LOCOMO_COMMAND='python -c "print(0)"' \
  seam bench external --scope locomo --format json --output /tmp/run.json
jq '.status, .cases[0].status, .cases[0].returncode' /tmp/run.json

# Strict mode should fail
seam bench external --strict; echo "exit=$?"

# Reserved flag pointer
seam bench external --plan --quickstart locomo; echo "exit=$?"

# Tests
pytest test_seam_all/test_external_memory_benchmarks.py -v
pytest test_seam_all -x

# Continuity
python -m tools.history.verify_continuity
python -m tools.history.verify_integrity
```

## 8. HISTORY entry template

```yaml
id: NNN  # next available
date: <ISO date>
agent: deepseek
status: done
topics: [benchmark, command, protocol, verify]
commits: [<sha>]
refs:
  - benchmarks/registry/memory_benchmarks.json
  - seam_runtime/external_memory_benchmarks.py
  - seam_runtime/cli.py
  - tools/run_external_memory_benchmarks.py
  - benchmarks/external/README.md
  - test_seam_all/test_external_memory_benchmarks.py
  - .github/workflows/ci.yml
  - docs/SOP_EXTERNAL_BENCH_PHASE1_REGISTRY.md
supersedes: <last benchmark-topic entry id>
tokens: ~<count>
body: |
  Landed Phases 1+2 of Track I (external memory benchmarks). Brought the
  registry, validator, plan, and command-env runner across from
  origin/bench/add-memory-benchmark-registry. Added `seam bench external`
  CLI subcommand. Added CI artifact for the runner plan. No adapter
  implementations yet; SOP 1 (SEAM LoCoMo adapter) is next.

  Verification: pytest test_seam_all/test_external_memory_benchmarks.py
  passes (N tests). seam bench external --plan lists all required
  benchmarks as missing on a clean machine. seam bench external --strict
  exits non-zero with no env vars set. Continuity and integrity verifiers
  pass.
```

## 9. Pitfalls

- **Do not pull the entire `bench/add-memory-benchmark-registry` branch.** It contains divergent unrelated changes (removed HISTORY.md content, removed docs, removed streams). Only copy the four files in section 4.
- **Do not call `seam benchmark gate` from the external runner.** External benchmarks have a separate report shape and a separate gate path. They do not feed `seam benchmark gate` until Track K (BIL bundles) wraps them.
- **Do not bundle any real benchmark dataset.** That is the adapter's job per SOP 1+. This PR ships zero data.
- **Do not name the subcommand `seam benchmark external`.** The existing `seam benchmark` namespace is for SEAM's internal glassbox suite. `seam bench external` is the new namespace for external comparator benchmarks. Keep them visually distinct.
- **Do not promote `--strict` into release CI yet.** That happens in SOP 5 once at least one adapter and one comparator are stable.
- **Per AGENTS.md security rules**, do not commit any session URLs, API keys, or `.env` values in tests, docs, or the registry.

## 10. Estimated scope

- ~400-700 lines net new code (most of it tests)
- One commit or a tight series
- Single review cycle
- No new third-party dependencies
- No runtime regression risk (the new module is import-only until invoked)

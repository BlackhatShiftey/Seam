# SEAM Code Layout

This file separates current code from inactive or generated code so agents do
not have to infer what works from directory names alone.

## Active Runtime

- `seam_runtime/` - packaged runtime, dashboard, storage, retrieval, model, and benchmark code.
- `seam_runtime/retrieval_orchestrator/` - multi-leg retrieval orchestrator (planner, adapters, merger) powering `seam retrieve`, the MCP tool, dashboard retrieval, and the benchmark suite. Promoted from `experimental/` in HISTORY#284.
- `seam.py` - console entrypoint module for `seam` and `seam-benchmark`.
- `test_seam_all/test_seam.py` - primary regression suite. Local `test_seam_*.db`
  artifacts live in ignored `test_seam/` so root stays clean.

## Active Tooling

- `tools/history/` - canonical history, index, integrity, and snapshot tools.
- `tools/*.py` - active benchmark/projection helper scripts.
- `scripts/` - active operator scripts and guarded runners.
- `installers/` - active installation entrypoints and installer docs.

## Active Prototypes

- `experimental/` - now holds only the browser dashboard prototype below. The
  former `experimental/retrieval_orchestrator/` was load-bearing runtime code
  (imported by `cli`, `mcp`, `dashboard`, and `benchmarks`) and has been
  promoted to `seam_runtime/retrieval_orchestrator/` (see HISTORY#284); it is
  no longer "experimental".
- `experimental/webui/` - active IDE-like browser dashboard prototype and
  visual target for the future REST API GUI. It is a non-Python (TypeScript)
  prototype, is not imported by the runtime, and is not packaged.

## Inactive Code

- `archive/code/` - retired code and local generated build copies. Nothing in
  this folder is active, imported, tested, or packaged.

## Generated / Local-Only Code

- `build/` and `archive/code/generated-build*/` are generated build copies and
  are ignored by git.
- `test_seam/` contains local isolated SQLite databases produced by test runs.
  It is not project source, runtime truth, roadmap evidence, or useful context
  for normal agent scans.
- `__pycache__/`, `.pytest_cache/`, `.venv/`, and `*.egg-info/` are local
  environment or packaging artifacts.

## Agent Rule

For normal development, read active runtime/tooling/prototype paths first. Do
not scan `archive/code/` unless the task explicitly asks for historical or
retired code.

## Search Rule

`.rgignore` excludes inactive, generated, and cache-heavy paths from default
searches. Use explicit paths or `rg --no-ignore` only when investigating archive
or retired-code history on purpose.

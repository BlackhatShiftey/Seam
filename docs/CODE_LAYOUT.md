# SEAM Code Layout

This file separates current code from inactive or generated code so agents do
not have to infer what works from directory names alone.

## Active Runtime

- `seam_runtime/` - packaged runtime, dashboard, storage, retrieval, model, and benchmark code.
- `seam.py` - console entrypoint module for `seam` and `seam-benchmark`.
- `test_seam_all/test_seam.py` - primary regression suite. Local `test_seam_*.db`
  artifacts live in `test_seam/` and remain ignored.

## Active Tooling

- `tools/history/` - canonical history, index, integrity, and snapshot tools.
- `tools/*.py` - active benchmark/projection helper scripts.
- `scripts/` - active operator scripts and guarded runners.
- `installers/` - active installation entrypoints and installer docs.

## Active Prototypes

- `experimental/` - live experimental modules. These may be imported by active
  code or tests, so they are not archived. Treat them as less stable than
  `seam_runtime/`, but not dead code.
- `experimental/webui/` - active IDE-like browser dashboard prototype and
  visual target for the future REST API GUI. It is not wired into packaged
  runtime behavior yet.

## Inactive Code

- `archive/code/` - retired code and local generated build copies. Nothing in
  this folder is active, imported, tested, or packaged.

## Generated / Local-Only Code

- `build/` and `archive/code/generated-build*/` are generated build copies and
  are ignored by git.
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

# Conventions

## Names and Concepts

- Preserve the distinction between `SEAM`, `MIRL`, and `PACK`.
- Keep record IDs, namespace behavior, and scope semantics stable unless the task explicitly requires a change.
- Treat symbol promotion as an auditable compaction step, not a silent rewrite.

## Code Style

- Prefer Python stdlib unless a new dependency is clearly justified.
- Keep public helpers in `seam.py` thin and delegate behavior into `seam_runtime`.
- Preserve existing `unittest` style unless there is a strong reason to introduce a new test runner.
- Keep CLI output machine-friendly where practical, especially JSON-returning commands.

## Change Safety

- Do not silently rename CLI commands, flags, MIRL fields, or persisted table behavior.
- When changing storage, retrieval, or symbol flows, add or update a focused test in `test_seam.py`.
- Avoid mutating checked-in SQLite files. Generate new local DBs for experiments instead.

## Documentation Expectations

- If a change affects MIRL semantics, retrieval behavior, model integration, or symbol handling, update the corresponding doc in `docs/`.
- Prefer documenting commands and repo structure in shared project docs rather than burying them in tool-specific skills.

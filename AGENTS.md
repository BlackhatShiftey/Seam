# AGENTS

Shared operating notes for any coding agent working in the SEAM project.

## Scope

- Repository root: `C:\Users\iwana\OneDrive\Documents\Codex`
- Runtime package: `C:\Users\iwana\OneDrive\Documents\Codex\seam_runtime`
- CLI entrypoint: `C:\Users\iwana\OneDrive\Documents\Codex\seam.py`
- Primary test file: `C:\Users\iwana\OneDrive\Documents\Codex\test_seam.py`

## Read This First

1. Read `README.md` for the project-level intent and quick-start commands.
2. Read `docs/PROJECT_MAP.md` for file responsibilities before editing.
3. Read `docs/COMMANDS.md` before running tests or CLI flows.
4. Read `docs/CONVENTIONS.md` before changing public behavior, schemas, or prompts.

## Working Agreements

- Treat `MIRL`, `PACK`, `SEAM`, symbol promotion, and retrieval semantics as first-class concepts. Preserve those names unless the task explicitly asks for a rename.
- Prefer small, surgical edits over broad refactors.
- Keep CLI verbs stable unless a task explicitly calls for a breaking change.
- Avoid editing `.db` artifacts in the repo unless the user explicitly asks.
- Favor focused verification over broad reruns.
- Optimize for more useful retrieval with fewer tokens. Prefer changes that improve information density, deduplicate noisy results, and preserve exact/lossless behavior where SEAM claims reversibility.
- Do not act like a yes-man. If an assumption is weak or contradicted by the code, docs, or tests, call it out, explain why, and support the correction with local evidence.
- For retrieval and model work, inspect the current adapter path, run the smallest relevant test or benchmark, and update the corresponding docs when behavior changes.

## Task Routing

- CLI or command behavior: inspect `seam.py` and `seam_runtime/cli.py`
- Runtime orchestration: inspect `seam_runtime/runtime.py`
- MIRL or schema behavior: inspect `seam_runtime/mirl.py`, `docs/MIRL_V1.md`
- Retrieval or ranking behavior: inspect `seam_runtime/retrieval.py`, `vector.py`, `vector_adapters.py`, `docs/RETRIEVAL_EVAL_V1.md`
- Symbol work: inspect `seam_runtime/symbols.py`, `docs/SYMBOL_NURSERY.md`
- Model integration: inspect `seam_runtime/models.py`, `docs/SOP_MODEL_INTEGRATION.md`
- Storage or persistence: inspect `seam_runtime/storage.py`
- Parallel work lanes:
  - vector backend lane: `vector.py`, `vector_adapters.py`, backend-specific tests
  - retrieval and eval lane: `retrieval.py`, `evals.py`, `docs/RETRIEVAL_EVAL_V1.md`
  - runtime and docs lane: `runtime.py`, `README.md`, `docs/SOP_MODEL_INTEGRATION.md`, `AGENTS.md`

## Verification

- Default test pass: `python -m unittest test_seam.py`
- CLI help: `python seam.py --help`
- When changing one subsystem, run the smallest relevant command or test that proves the behavior.
- Retrieval changes should verify both relevance and token efficiency. Check expected hits, duplicate suppression, and whether exact pack round-trip behavior remains intact.

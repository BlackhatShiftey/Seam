# SEAM Holdout Fixtures

This directory is for publish-only benchmark fixtures.

Do not use holdout cases during normal development or tuning. Local JSON fixtures in this directory are ignored by git so held-out cases can stay private until publication.

Supported filenames:

- `lossless_cases.json`
- `readable_cases.json`
- `retrieval_gold_fixtures.json`
- `long_context_cases.json`
- `agent_tasks.json`

Run a holdout suite only when publishing or auditing a benchmark claim:

```powershell
python seam.py benchmark run all --holdout --confirm-holdout
```

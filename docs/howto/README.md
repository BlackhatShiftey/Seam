# SEAM How-To Runbooks

All runbooks below are command-first and safe to copy/paste.

## 1) Ingest and Retrieve Memory

```powershell
.\.venv\Scripts\seam.exe compile-nl "We need durable memory for AI systems." --persist
.\.venv\Scripts\seam.exe index
.\.venv\Scripts\seam.exe retrieve "durable memory" --budget 5 --trace
.\.venv\Scripts\seam.exe context "durable memory" --view prompt
```

Success checklist:

- retrieval returns at least one candidate
- context output includes records/citations

## 2) Run Guarded Real-Adapter Validation

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_real_adapters_guarded.ps1
```

Optional smoke-only run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_real_adapters_guarded.ps1 -SkipPytest
```

Success checklist:

- runner exits cleanly
- pgvector container cleanup completes

## 3) Archive Benchmarks to Documents

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\store_benchmark.ps1 -Suite all
```

Success checklist:

- run folder created under `%USERPROFILE%\Documents\SEAM\benchmarks`
- `publication_manifest.json` and `case_hashes.json` exist
- daily `_index.json` updated

## 4) Recover from Interrupted Local Runs

```powershell
docker ps --filter "name=seam-pgvector-test"
docker rm -f seam-pgvector-test
.\.venv\Scripts\seam.exe doctor
.\.venv\Scripts\python.exe -m unittest test_seam.SeamTests.test_dashboard_snapshot_renders_runtime_metrics
```

Success checklist:

- no stale test container remains
- doctor returns `PASS`
- smoke test passes


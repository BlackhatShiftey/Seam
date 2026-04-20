# SEAM Troubleshooting (Documented Errors)

Use this as the first-stop error playbook. Every section includes exact fix and verify commands.

## Error: `ModuleNotFoundError: No module named 'textual'`

### Symptom

Running `seam-dash` or Textual tests fails with missing `textual`.

### Fix (Windows)

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dash]"
```

### Fix (Linux / WSL2)

```bash
./.venv/bin/python -m pip install -e ".[dash]"
```

### Verify

```powershell
.\.venv\Scripts\python.exe -m pip show textual
.\.venv\Scripts\python.exe -m unittest test_seam.SeamTests.test_textual_dashboard_mounts_core_panels
```

## Error: `SEAM doctor: FAIL` with missing required deps

### Symptom

`seam doctor` shows missing `rich`, `chromadb`, or `tiktoken`.

### Fix (Windows)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\seam.exe doctor
```

### Fix (Linux / WSL2)

```bash
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/seam doctor
```

### Verify

Look for:

- `SEAM doctor: PASS`
- `Required deps: OK`

## Error: `PgVector: configured but unreachable`

### Symptom

`seam doctor` shows PgVector is configured but not reachable.

### Fix (Docker local Postgres with pgvector)

```powershell
docker compose up -d
$env:SEAM_PGVECTOR_DSN="postgresql://seam:local-test-password@localhost:5432/seam"
.\.venv\Scripts\seam.exe doctor
```

### Verify

Look for: `PgVector: reachable`.

## Error: Chroma path/index sync failure

### Symptom

`seam index --vector-backend chroma` fails due to path or permissions.

### Fix (Windows)

```powershell
New-Item -ItemType Directory -Force .seam_chroma | Out-Null
.\.venv\Scripts\seam.exe index --vector-backend chroma --vector-path .seam_chroma
```

### Fix (Linux / WSL2)

```bash
mkdir -p .seam_chroma
./.venv/bin/seam index --vector-backend chroma --vector-path .seam_chroma
```

### Verify

The index command completes without an error and reports synced ids.

## Error: Benchmark bundle verification failure

### Symptom

`seam benchmark verify <bundle>` reports hash mismatch or failed validation.

### Fix

Re-run benchmark and produce a new verified bundle from current environment:

```powershell
.\.venv\Scripts\seam.exe benchmark run all --persist --output seam-benchmark-report.json
.\.venv\Scripts\seam.exe benchmark verify seam-benchmark-report.json
```

### Verify

Benchmark verification output indicates `PASS`.

## Do-Not-Proceed Blockers

Stop and resolve before continuing:

- `SEAM doctor: FAIL`
- Lossless roundtrip failures
- Benchmark verification hash mismatch for published claims
- PgVector configured but unreachable when pgvector is the selected backend


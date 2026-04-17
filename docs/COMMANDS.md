# Commands

Run commands from `C:\Users\iwana\OneDrive\Documents\Codex` unless noted otherwise.

## Copy-Paste Setup

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
notepad .env
.\scripts\setup-seam.ps1 -UserName "your-user" -DatabaseName "seam"
```

## Basic Inspection

```powershell
python seam.py --help
python -m unittest test_seam.py
```

## Local Pgvector Setup

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env -ErrorAction SilentlyContinue
notepad .env
. .\scripts\pgvector-up.ps1
python -m unittest test_seam.py
```

## CLI Quick Start

```powershell
python seam.py --db seam.db compile-nl "We need a translator back into natural language for memory workflows." --persist
python seam.py --db seam.db promote-symbols --min-frequency 1
python seam.py --db seam.db reindex
python seam.py --db seam.db search "translator natural language" --budget 3
python seam.py --db seam.db export-symbols
```

## Useful Targeted Commands

```powershell
python seam.py --db seam.db stats
python seam.py --db seam.db trace clm:5
python seam.py --db seam.db pack clm:1,clm:2 --mode context
python seam.py --db seam.db decompile clm:1,clm:2 --mode expanded
```

## Environment-Driven Embeddings

```powershell
$env:SEAM_EMBEDDING_PROVIDER="openai"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
$env:OPENAI_API_KEY="..."
python -m unittest test_seam.py
```

## Working Directory Notes

- If your shell is already inside `seam_runtime`, run root commands as `python ..\seam.py ...`
- Favor `python -m unittest test_seam.py` over ad hoc manual runs when changing behavior
- `scripts\setup-seam.ps1` is the fastest path once `.env` has your private password in it
- `scripts\pgvector-up.ps1` exports a passwordless `SEAM_PGVECTOR_TEST_DSN` and sets `PGPASSWORD` only in the current session

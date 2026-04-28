# PgVector Maintenance Ledger

Current stable facts:

- Normal tests run without PgVector credentials.
- Docker real-adapter tests use temporary runtime credentials from `scripts/run_real_adapters_guarded.ps1`.
- Local operator PgVector credentials must live outside the repo, preferably under `Documents\SEAM\local\.env` on Windows or `$HOME/.config/seam/.env` on POSIX systems.
- Repo-root `.env` files are ignored and should not be used as durable secret storage.

Useful checks:

```powershell
python -m pytest test_seam.py tools/history/test_history_tools.py
powershell -ExecutionPolicy Bypass -File scripts\run_real_adapters_guarded.ps1 -PgPort 55433
python -m tools.history.verify_continuity
```

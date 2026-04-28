# Docker Maintenance Ledger

Current stable facts:

- Docker-backed SEAM real-adapter validation uses `scripts/run_real_adapters_guarded.ps1`.
- The guarded runner generates a temporary Postgres password at runtime and does not require repo-root `.env`.
- The default guarded port is `55432`; if it is occupied, use `-PgPort <free-port>`.
- On 2026-04-26, stale container `seam-pgvector` was stopped after it held port `55432`; volumes were left intact. See `HISTORY#084`.
- Docker maintenance history is routed by `maintenance/docker`.

Verification commands:

```powershell
docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Ports}}"
Get-NetTCPConnection -State Listen -LocalPort 55432 -ErrorAction SilentlyContinue
python -m tools.history.build_context_pack --route maintenance/docker --token-budget 900
```

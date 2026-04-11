# Local Pgvector

Use this when you want a real Postgres + pgvector database behind SEAM without waiting on Cloud SQL or another hosted Postgres service.

## Start the database

```powershell
docker run -d --name seam-pgvector -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=seam -p 54329:5432 pgvector/pgvector:pg17
```

## Point SEAM at it

```powershell
$env:SEAM_PGVECTOR_DSN="postgresql://postgres:postgres@localhost:54329/seam"
python seam.py --db seam_validate.db validate-stack
```

## Use it for runtime commands

```powershell
python seam.py --db seam_live.db compile-nl "We need durable memory with a translator back into natural language." --persist
python seam.py --db seam_live.db reindex
python seam.py --db seam_live.db search "translator natural language" --budget 3
```

## Stop and remove it

```powershell
docker stop seam-pgvector
docker rm seam-pgvector
```

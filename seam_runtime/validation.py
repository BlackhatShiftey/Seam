from __future__ import annotations

import gc
import os
import urllib.error
from pathlib import Path
from tempfile import mkstemp
from typing import Any

from .models import embedding_settings_from_env
from .runtime import SeamRuntime, resolve_pgvector_dsn


def runtime_configuration_snapshot(pgvector_dsn: str | None = None) -> dict[str, Any]:
    settings = embedding_settings_from_env()
    resolved_pgvector_dsn = resolve_pgvector_dsn(pgvector_dsn)
    api_key_present = bool(os.environ.get(settings.api_key_env))
    cloud_provider = settings.provider not in {"hash", "local", "deterministic"}
    return {
        "embedding": {
            "provider": settings.provider,
            "model": settings.model,
            "base_url": settings.base_url,
            "api_key_env": settings.api_key_env,
            "api_key_present": api_key_present,
            "cloud_provider": cloud_provider,
            "configured": (not cloud_provider) or api_key_present,
        },
        "pgvector": {
            "dsn_present": bool(resolved_pgvector_dsn),
            "dsn": _redact_dsn(resolved_pgvector_dsn),
        },
    }


def validate_runtime_stack(store_path: str | Path, pgvector_dsn: str | None = None) -> dict[str, Any]:
    snapshot = runtime_configuration_snapshot(pgvector_dsn=pgvector_dsn)
    report: dict[str, Any] = {
        "configuration": snapshot,
        "checks": [],
    }
    report["checks"].append(_embedding_smoke_check())
    report["checks"].append(_pgvector_smoke_check(store_path=store_path, pgvector_dsn=pgvector_dsn))
    return report


def _embedding_smoke_check() -> dict[str, Any]:
    settings = embedding_settings_from_env()
    if settings.provider in {"hash", "local", "deterministic"}:
        return {
            "name": "embedding_provider",
            "status": "ok",
            "message": "Using deterministic local embeddings; cloud smoke test skipped.",
            "provider": settings.provider,
        }
    api_key = os.environ.get(settings.api_key_env)
    if not api_key:
        return {
            "name": "embedding_provider",
            "status": "blocked",
            "message": f"Missing API key in {settings.api_key_env}; cannot run live cloud embedding smoke test.",
            "provider": settings.provider,
            "model": settings.model,
        }
    runtime = SeamRuntime("validation_cloud_smoke.db")
    try:
        vector = runtime.embedding_model.embed("SEAM validation embedding smoke test")
        return {
            "name": "embedding_provider",
            "status": "ok",
            "message": "Live cloud embedding smoke test passed.",
            "provider": settings.provider,
            "model": settings.model,
            "dimension": len(vector),
        }
    except urllib.error.HTTPError as exc:
        return {
            "name": "embedding_provider",
            "status": "blocked",
            "message": f"Cloud embedding smoke test failed with HTTP {exc.code}.",
            "provider": settings.provider,
            "model": settings.model,
            "http_status": exc.code,
            "reason": getattr(exc, "reason", None),
        }
    except urllib.error.URLError as exc:
        return {
            "name": "embedding_provider",
            "status": "blocked",
            "message": "Cloud embedding smoke test could not reach the endpoint.",
            "provider": settings.provider,
            "model": settings.model,
            "reason": str(exc.reason),
        }
    finally:
        try:
            Path("validation_cloud_smoke.db").unlink(missing_ok=True)
        except OSError:
            pass


def _pgvector_smoke_check(store_path: str | Path, pgvector_dsn: str | None = None) -> dict[str, Any]:
    resolved_pgvector_dsn = resolve_pgvector_dsn(pgvector_dsn)
    if not resolved_pgvector_dsn:
        return {
            "name": "pgvector",
            "status": "blocked",
            "message": "Missing pgvector DSN; set SEAM_PGVECTOR_DSN or pass --pgvector-dsn.",
        }
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return {
            "name": "pgvector",
            "status": "blocked",
            "message": "Missing psycopg dependency; install psycopg[binary] to validate the pgvector adapter.",
        }
    fd, temp_db_name = mkstemp(prefix="seam_pgvector_validate_", suffix=".db")
    os.close(fd)
    temp_db = Path(temp_db_name)
    try:
        runtime = SeamRuntime(temp_db, pgvector_dsn=resolved_pgvector_dsn)
        batch = runtime.compile_nl(
            "We need a translator back into natural language for memory workflows.",
            source_ref="validation://pgvector",
        )
        runtime.persist_ir(batch)
        result = runtime.search_ir("translator natural language", budget=3)
        top_ids = [candidate.record.id for candidate in result.candidates]
        report = {
            "name": "pgvector",
            "status": "ok",
            "message": "Pgvector adapter indexed and searched successfully.",
            "adapter": getattr(runtime.vector_adapter, "name", "unknown"),
            "top_ids": top_ids,
        }
        del runtime
        gc.collect()
        return report
    finally:
        try:
            temp_db.unlink(missing_ok=True)
        except OSError:
            pass


def _redact_dsn(dsn: str | None) -> str | None:
    if dsn is None:
        return None
    if "@" not in dsn:
        return dsn
    prefix, suffix = dsn.split("@", 1)
    if "://" in prefix:
        scheme, credentials = prefix.split("://", 1)
        username = credentials.split(":", 1)[0]
        return f"{scheme}://{username}:***@{suffix}"
    return f"***@{suffix}"

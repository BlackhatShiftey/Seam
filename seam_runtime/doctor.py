from __future__ import annotations

import os
import sys
from importlib.util import find_spec

from .installer import default_runtime_db_path
from .lossless import benchmark_text_lossless
from .runtime import SeamRuntime


def check_pgvector(dsn: str | None) -> dict[str, object]:
    if not dsn:
        return {"configured": False}
    try:
        import psycopg
        conn = psycopg.connect(dsn)
        conn.close()
        return {"configured": True, "reachable": True}
    except Exception as exc:
        return {"configured": True, "reachable": False, "error": str(exc)}


def build_doctor_report() -> dict[str, object]:
    runtime = SeamRuntime(":memory:")
    batch = runtime.compile_nl("SEAM doctor smoke test for durable local memory.")
    smoke_ok = bool(batch.records)
    lossless_result = benchmark_text_lossless(
        "\n".join(["SEAM preserves exact context while compressing token usage for lossless recovery."] * 12),
        min_token_savings=0.30,
    )
    pgvector_dsn = os.environ.get("SEAM_PGVECTOR_DSN")
    dependencies = {
        "rich": find_spec("rich") is not None,
        "chromadb": find_spec("chromadb") is not None,
        "tiktoken": find_spec("tiktoken") is not None,
        "psycopg": find_spec("psycopg") is not None,
        "sentence_transformers": find_spec("sentence_transformers") is not None,
    }
    required_dependencies = ["rich", "chromadb", "tiktoken"]
    missing_required = [name for name in required_dependencies if not dependencies.get(name)]
    deps_ok = not missing_required
    status = "PASS" if smoke_ok and lossless_result.roundtrip_match and deps_ok else "FAIL"
    return {
        "status": status,
        "python": sys.version.split()[0],
        "db_mode": "in-memory",
        "default_db_path": default_runtime_db_path(),
        "smoke_compile": {
            "status": "PASS" if smoke_ok else "FAIL",
            "record_count": len(batch.records),
        },
        "lossless": {
            "status": "PASS" if lossless_result.roundtrip_match else "FAIL",
            "token_estimator": lossless_result.artifact.token_estimator,
            "token_savings_ratio": round(lossless_result.artifact.token_savings_ratio, 6),
        },
        "pgvector": check_pgvector(pgvector_dsn),
        "dependencies": dependencies,
        "required_dependencies": required_dependencies,
        "missing_required_dependencies": missing_required,
    }

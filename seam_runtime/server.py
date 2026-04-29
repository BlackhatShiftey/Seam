from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .installer import default_runtime_db_path
from .mirl import IRBatch
from .runtime import SeamRuntime


def _require_fastapi() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, Request
    except ImportError as exc:  # pragma: no cover - exercised when optional extra is absent
        raise RuntimeError('SEAM server dependencies are not installed. Run: pip install -e ".[server]"') from exc
    return Depends, FastAPI, Header, HTTPException, Request


def _require_uvicorn() -> Any:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised when optional extra is absent
        raise RuntimeError('Uvicorn is not installed. Run: pip install -e ".[server]"') from exc
    return uvicorn


@dataclass
class RateLimiter:
    limit_per_minute: int = 0
    hits: dict[str, list[float]] = field(default_factory=dict)

    def check(self, key: str) -> bool:
        if self.limit_per_minute <= 0:
            return True
        now = time.monotonic()
        window_start = now - 60.0
        recent = [stamp for stamp in self.hits.get(key, []) if stamp >= window_start]
        if len(recent) >= self.limit_per_minute:
            self.hits[key] = recent
            return False
        recent.append(now)
        self.hits[key] = recent
        return True


def _rate_limit_from_env() -> int:
    raw = os.environ.get("SEAM_API_RATE_LIMIT_PER_MINUTE") or os.environ.get("SEAM_API_RATE_LIMIT") or "0"
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _client_key(request: Any, authorization: str | None = None) -> str:
    if authorization:
        return authorization
    client = getattr(request, "client", None)
    return getattr(client, "host", "local") or "local"


def create_app(runtime: SeamRuntime | None = None) -> Any:
    Depends, FastAPI, Header, HTTPException, Request = _require_fastapi()
    globals()["Request"] = Request
    runtime = runtime or SeamRuntime(default_runtime_db_path())
    limiter = RateLimiter(_rate_limit_from_env())
    token = os.environ.get("SEAM_API_TOKEN")

    app = FastAPI(title="SEAM Runtime API", version="0.1")

    def guard(request: Request, authorization: str | None = Header(default=None)) -> None:
        if not limiter.check(_client_key(request, authorization)):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        if token:
            expected = f"Bearer {token}"
            if authorization != expected:
                raise HTTPException(status_code=401, detail="Missing or invalid bearer token")

    def rate_limit_only(request: Request, authorization: str | None = Header(default=None)) -> None:
        if not limiter.check(_client_key(request, authorization)):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    @app.get("/health", dependencies=[Depends(rate_limit_only)])
    def health() -> dict[str, object]:
        return {"status": "ok", "store_path": runtime.store.path}

    @app.get("/stats", dependencies=[Depends(guard)])
    def stats() -> dict[str, object]:
        return runtime.store.get_stats()

    @app.post("/compile", dependencies=[Depends(guard)])
    def compile_text(payload: dict[str, object]) -> dict[str, object]:
        text = str(payload.get("text", ""))
        if not text.strip():
            raise HTTPException(status_code=400, detail="text is required")
        batch = runtime.compile_nl(
            text,
            source_ref=str(payload.get("source_ref") or "api://compile"),
            ns=str(payload.get("ns") or "local.default"),
            scope=str(payload.get("scope") or "thread"),
        )
        result: dict[str, object] = {"records": batch.to_json()}
        if bool(payload.get("persist", False)):
            result["persist"] = runtime.persist_ir(batch).to_dict()
        return result

    @app.post("/compile-dsl", dependencies=[Depends(guard)])
    def compile_dsl_endpoint(payload: dict[str, object]) -> dict[str, object]:
        dsl = str(payload.get("dsl", ""))
        if not dsl.strip():
            raise HTTPException(status_code=400, detail="dsl is required")
        batch = runtime.compile_dsl(
            dsl,
            ns=str(payload.get("ns") or "local.default"),
            scope=str(payload.get("scope") or "project"),
        )
        result: dict[str, object] = {"records": batch.to_json()}
        if bool(payload.get("persist", False)):
            result["persist"] = runtime.persist_ir(batch).to_dict()
        return result

    @app.get("/search", dependencies=[Depends(guard)])
    def search(query: str, scope: str | None = None, budget: int = 5, lens: str = "general") -> dict[str, object]:
        return runtime.search_ir(query=query, scope=scope, budget=budget, lens=lens).to_dict()

    @app.post("/context", dependencies=[Depends(guard)])
    def context(payload: dict[str, object]) -> dict[str, object]:
        query = str(payload.get("query", ""))
        if not query.strip():
            raise HTTPException(status_code=400, detail="query is required")
        budget = int(payload.get("budget") or 5)
        search_result = runtime.search_ir(
            query=query,
            scope=payload.get("scope") if isinstance(payload.get("scope"), str) else None,
            budget=budget,
            lens=str(payload.get("lens") or "general"),
        )
        record_ids = [candidate.record.id for candidate in search_result.candidates]
        pack = runtime.pack_ir(
            record_ids=record_ids,
            lens=str(payload.get("lens") or "rag"),
            budget=int(payload.get("pack_budget") or 512),
            mode=str(payload.get("mode") or "context"),
        )
        return {"query": query, "candidates": search_result.to_dict()["candidates"], "pack": pack.to_dict()}

    @app.post("/lossless-compress", dependencies=[Depends(guard)])
    def lossless_compress(payload: dict[str, object]) -> dict[str, object]:
        from .lossless import benchmark_text_lossless

        text = str(payload.get("text", ""))
        if not text.strip():
            raise HTTPException(status_code=400, detail="text is required")
        result = benchmark_text_lossless(
            text,
            codec=str(payload.get("codec") or "auto"),
            transform=str(payload.get("transform") or "auto"),
            tokenizer=str(payload.get("tokenizer") or "auto"),
            min_token_savings=float(payload.get("min_token_savings") or 0.30),
        )
        return result.to_dict(include_machine_text=bool(payload.get("include_machine_text", False)))

    @app.post("/persist", dependencies=[Depends(guard)])
    def persist(payload: dict[str, object]) -> dict[str, object]:
        records = payload.get("records")
        if not isinstance(records, list):
            raise HTTPException(status_code=400, detail="records list is required")
        return runtime.persist_ir(IRBatch.from_json(records)).to_dict()

    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    db: str | Path | None = None,
    reload: bool = False,
    workers: int = 1,
) -> None:
    _require_fastapi()
    uvicorn = _require_uvicorn()
    os.environ["SEAM_SERVER_DB"] = str(db or default_runtime_db_path())
    uvicorn.run(
        "seam_runtime.server:create_app_from_env",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        factory=True,
    )


def create_app_from_env() -> Any:
    return create_app(SeamRuntime(os.environ.get("SEAM_SERVER_DB") or default_runtime_db_path()))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the SEAM REST API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=default_runtime_db_path())
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    run_server(host=args.host, port=args.port, db=args.db, reload=args.reload, workers=args.workers)


if __name__ == "__main__":
    main()

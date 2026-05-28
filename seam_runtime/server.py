from __future__ import annotations

import argparse
import hashlib
import hmac
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .installer import default_runtime_db_path
from .mirl import IRBatch
from .runtime import SeamRuntime

LOGGER = logging.getLogger(__name__)


@dataclass
class ShutdownState:
    shutting_down: bool = False
    in_flight: int = 0
    _lock: Any = field(default_factory=threading.Lock, repr=False, compare=False)

    def begin_request(self) -> bool:
        with self._lock:
            if self.shutting_down:
                return False
            self.in_flight += 1
            return True

    def end_request(self) -> None:
        with self._lock:
            self.in_flight = max(0, self.in_flight - 1)

    def trigger_shutdown(self) -> None:
        with self._lock:
            self.shutting_down = True

    def snapshot(self) -> tuple[bool, int]:
        with self._lock:
            return (self.shutting_down, self.in_flight)

    def wait_drain(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                if self.in_flight == 0:
                    return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.05, remaining))


def _shutdown_timeout_from_env() -> float:
    raw = os.environ.get("SEAM_SHUTDOWN_TIMEOUT") or "30"
    try:
        value = float(raw)
    except ValueError:
        return 30.0
    return max(1.0, value)


def _cleanup_runtime(runtime: SeamRuntime) -> None:
    try:
        runtime.store.close()
    except Exception:
        LOGGER.warning("Error closing store", exc_info=True)
    vector_adapter = getattr(runtime, "vector_adapter", None)
    if vector_adapter is not None and hasattr(vector_adapter, "close"):
        try:
            vector_adapter.close()
        except Exception:
            LOGGER.warning("Error closing vector adapter", exc_info=True)


class ShutdownMiddleware:
    def __init__(self, app: Any, state: ShutdownState) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        if not self.state.begin_request():
            from starlette.responses import JSONResponse

            response = JSONResponse({"status": "shutting_down"}, status_code=503)
            await response(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            self.state.end_request()


def _require_fastapi() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
    except ImportError as exc:  # pragma: no cover - exercised when optional extra is absent
        raise RuntimeError('SEAM server dependencies are not installed. Run: pip install -e ".[server]"') from exc
    return Depends, FastAPI, Header, HTTPException, Query, Request


def _require_uvicorn() -> Any:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised when optional extra is absent
        raise RuntimeError('Uvicorn is not installed. Run: pip install -e ".[server]"') from exc
    return uvicorn


@dataclass
class RateLimiter:
    limit_per_minute: int = 0
    max_keys: int = 10000
    hits: dict[str, list[float]] = field(default_factory=dict)
    _lock: Any = field(default_factory=threading.Lock, repr=False, compare=False)

    def check(self, key: str) -> bool:
        if self.limit_per_minute <= 0:
            return True
        with self._lock:
            now = time.monotonic()
            window_start = now - 60.0
            self._purge(window_start)
            if key not in self.hits and len(self.hits) >= self.max_keys:
                oldest_key = min(self.hits, key=lambda item: self.hits[item][-1] if self.hits[item] else 0.0)
                self.hits.pop(oldest_key, None)
            recent = [stamp for stamp in self.hits.get(key, []) if stamp >= window_start]
            if len(recent) >= self.limit_per_minute:
                self.hits[key] = recent
                return False
            recent.append(now)
            self.hits[key] = recent
            return True

    def _purge(self, window_start: float) -> None:
        stale = [key for key, stamps in self.hits.items() if not any(stamp >= window_start for stamp in stamps)]
        for key in stale:
            self.hits.pop(key, None)


def _rate_limit_from_env() -> int:
    raw = os.environ.get("SEAM_API_RATE_LIMIT_PER_MINUTE") or os.environ.get("SEAM_API_RATE_LIMIT") or "0"
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _rate_limit_max_keys_from_env() -> int:
    raw = os.environ.get("SEAM_API_RATE_LIMIT_MAX_KEYS") or "10000"
    try:
        return max(1, int(raw))
    except ValueError:
        return 10000


def _max_body_bytes_from_env() -> int:
    raw = os.environ.get("SEAM_API_MAX_BODY_BYTES") or "5000000"
    try:
        return max(0, int(raw))
    except ValueError:
        return 5000000


def _cors_origins_from_env() -> list[str]:
    raw = os.environ.get("SEAM_API_CORS_ORIGINS")
    if raw is None:
        return ["http://127.0.0.1:5173", "http://localhost:5173"]
    if raw.strip().lower() in {"", "0", "false", "off", "none"}:
        return []
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def _client_key(request: Any, authorization: str | None = None) -> str:
    if authorization:
        return hashlib.sha256(authorization.encode()).hexdigest()
    client = getattr(request, "client", None)
    return getattr(client, "host", "local") or "local"


class _RequestBodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, app: Any, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if self.max_body_bytes <= 0 or scope.get("type") != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length.decode("ascii")) > self.max_body_bytes:
                    await _send_body_too_large(scope, send, self.max_body_bytes)
                    return
            except ValueError:
                pass
        received = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await _send_body_too_large(scope, send, self.max_body_bytes)


async def _send_body_too_large(scope: dict[str, Any], send: Any, max_body_bytes: int) -> None:
    from starlette.responses import JSONResponse

    async def empty_receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    response = JSONResponse({"detail": f"Request body exceeds {max_body_bytes} bytes"}, status_code=413)
    await response(scope, empty_receive, send)


def create_app(
    runtime: SeamRuntime | None = None,
    shutdown_state: ShutdownState | None = None,
) -> Any:
    Depends, FastAPI, Header, HTTPException, Query, Request = _require_fastapi()
    # Required: `from __future__ import annotations` defers annotation evaluation,
    # so FastAPI's typing.get_type_hints must find `Request` in module globals.
    # fastapi is a lazy import (optional extra), so we publish it here. Idempotent:
    # the class is the same across create_app() calls.
    globals()["Request"] = Request
    if runtime is None:
        db_path = os.environ.get("SEAM_SERVER_DB") or default_runtime_db_path()
        runtime = SeamRuntime(db_path)
    limiter = RateLimiter(_rate_limit_from_env(), max_keys=_rate_limit_max_keys_from_env())
    token = os.environ.get("SEAM_API_TOKEN")
    state = shutdown_state or ShutdownState()

    app = FastAPI(title="SEAM Runtime API", version="0.1")
    app.add_middleware(ShutdownMiddleware, state=state)
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=_max_body_bytes_from_env())
    cors_origins = _cors_origins_from_env()
    if cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    def guard(request: Request, authorization: str | None = Header(default=None)) -> None:
        if not limiter.check(_client_key(request, authorization)):
            LOGGER.warning("Rate limit exceeded for client %s", request.client.host if request.client else "unknown")
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        if token:
            expected = f"Bearer {token}"
            if not authorization or not hmac.compare_digest(authorization, expected):
                LOGGER.warning("Auth failed for client %s", request.client.host if request.client else "unknown")
                raise HTTPException(status_code=401, detail="Missing or invalid bearer token")

    def rate_limit_only(request: Request, authorization: str | None = Header(default=None)) -> None:
        if not limiter.check(_client_key(request, authorization)):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

    @app.get("/health", dependencies=[Depends(rate_limit_only)])
    def health() -> dict[str, object]:
        return {"status": "ok"}

    @app.get("/stats", dependencies=[Depends(guard)])
    def stats() -> dict[str, object]:
        return runtime.store.get_stats()

    @app.get("/trace", dependencies=[Depends(guard)])
    def trace(root_id: str) -> dict[str, object]:
        try:
            return runtime.store.trace(root_id).to_dict()
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.get("/tree", dependencies=[Depends(guard)])
    def tree(path: str = ".") -> dict[str, object]:
        root = _tree_root()
        try:
            start = _resolve_tree_path(root, path)
        except ValueError:
            raise HTTPException(status_code=400, detail="outside root")
        if not start.exists():
            raise HTTPException(status_code=404, detail="path not found")
        if not start.is_dir():
            raise HTTPException(status_code=400, detail="path is not a directory")
        max_depth = _tree_max_depth()
        max_entries = _tree_max_entries()
        counter: list[int] = [0]
        truncated: list[bool] = [False]
        tree_nodes = _walk_tree(
            start, root,
            depth=0, max_depth=max_depth, max_entries=max_entries,
            counter=counter, truncated=truncated,
        )
        return {
            "root": str(root),
            "path": path,
            "tree": tree_nodes,
            "truncated": truncated[0],
            "entries_seen": counter[0],
            "max_depth": max_depth,
            "max_entries": max_entries,
        }

    @app.post("/benchmark", dependencies=[Depends(guard)])
    def run_benchmark(payload: dict[str, object]) -> dict[str, object]:
        from .benchmarks import BENCHMARK_SUITES, run_benchmark_suite
        suite = str(payload.get("suite", "all"))
        if suite != "all" and suite not in BENCHMARK_SUITES:
            raise HTTPException(status_code=400, detail="invalid suite")
        persist = bool(payload.get("persist", False))
        holdout = bool(payload.get("holdout", False))
        if holdout:
            allow = os.environ.get("SEAM_API_ALLOW_BENCHMARK_HOLDOUT") == "1"
            if not allow:
                raise HTTPException(
                    status_code=403,
                    detail="holdout requires SEAM_API_ALLOW_BENCHMARK_HOLDOUT=1; see REPO_LEDGER Benchmark Publication Policy",
                )
            confirm = os.environ.get("SEAM_API_CONFIRM_HOLDOUT") == "1"
            if not confirm:
                raise HTTPException(
                    status_code=403,
                    detail="holdout requires SEAM_API_CONFIRM_HOLDOUT=1 (mirrors CLI --confirm-holdout)",
                )
        try:
            result = run_benchmark_suite(runtime, suite=suite, persist=persist, holdout=holdout)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result

    _last_cpu_times = None

    @app.get("/sys-metrics", dependencies=[Depends(guard)])
    def sys_metrics() -> dict[str, object]:
        nonlocal _last_cpu_times

        def _metric_value(value: float) -> dict[str, object]:
            return {"value": round(value, 1), "source": "live", "error": None}

        def _metric_unavailable(exc: Exception) -> dict[str, object]:
            return {"value": None, "source": "unavailable", "error": type(exc).__name__}

        def _metric_unsupported() -> dict[str, object]:
            return {"value": None, "source": "unsupported", "error": None}

        if not sys.platform.startswith("linux"):
            return {
                "cpu": _metric_unsupported(),
                "mem": _metric_unsupported(),
                "disk": _metric_unsupported(),
                "gpu": _metric_unsupported(),
                "net": _metric_unsupported(),
            }

        # CPU
        cpu_metric: dict[str, object]
        try:
            with open("/proc/stat", "r") as f:
                cpu_line = f.readline()
            parts = cpu_line.split()
            idle = float(parts[4]) + float(parts[5])
            total = sum(float(p) for p in parts[1:])
            if _last_cpu_times is not None:
                last_idle, last_total = _last_cpu_times
                idle_delta = idle - last_idle
                total_delta = total - last_total
                if total_delta > 0:
                    cpu_metric = _metric_value(100.0 * (1.0 - idle_delta / total_delta))
                else:
                    cpu_metric = {"value": None, "source": "live", "error": None}
            else:
                cpu_metric = {"value": None, "source": "live", "error": None}
            _last_cpu_times = (idle, total)
        except OSError as exc:
            cpu_metric = _metric_unavailable(exc)

        # Memory
        mem_metric: dict[str, object]
        try:
            mem_total = 0
            mem_avail = 0
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail = int(line.split()[1])
            if mem_total > 0:
                mem_metric = _metric_value(100.0 * (1.0 - (mem_avail / mem_total)))
            else:
                mem_metric = _metric_unavailable(ValueError("MemTotal zero or missing"))
        except OSError as exc:
            mem_metric = _metric_unavailable(exc)

        # Disk — target SEAM data directory filesystem
        disk_metric: dict[str, object]
        try:
            data_dir = Path(runtime.store.path).expanduser().resolve().parent
            st = os.statvfs(str(data_dir))
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            if total > 0:
                disk_metric = _metric_value(100.0 * (1.0 - (free / total)))
            else:
                disk_metric = _metric_unavailable(ValueError("zero total capacity"))
        except (OSError, FileNotFoundError) as exc:
            disk_metric = _metric_unavailable(exc)

        return {
            "cpu": cpu_metric,
            "mem": mem_metric,
            "disk": disk_metric,
            "gpu": _metric_unsupported(),
            "net": _metric_unsupported(),
        }

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
    def search(query: str, scope: str | None = None, budget: int = Query(default=5, ge=1, le=200), lens: str = "general") -> dict[str, object]:
        return runtime.search_ir(query=query, scope=scope, budget=budget, lens=lens).to_dict()

    @app.post("/context", dependencies=[Depends(guard)])
    def context(payload: dict[str, object]) -> dict[str, object]:
        query = str(payload.get("query", ""))
        if not query.strip():
            raise HTTPException(status_code=400, detail="query is required")
        budget = max(1, min(200, int(payload.get("budget") or 5)))
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
            budget=max(1, min(65536, int(payload.get("pack_budget") or 512))),
            mode=str(payload.get("mode") or "context"),
            persist=bool(payload.get("persist", False)),
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
    _validate_server_safety(host=host, workers=workers)
    os.environ["SEAM_SERVER_DB"] = str(db or default_runtime_db_path())

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum: int, frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        LOGGER.info("Received %s, initiating graceful shutdown", sig_name)
        # uvicorn handles SIGTERM/SIGINT gracefully by default
        # This handler just logs the signal
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    uvicorn.run(
        "seam_runtime.server:create_app_from_env",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        factory=True,
    )


def _validate_server_safety(host: str, workers: int) -> None:
    if _rate_limit_from_env() > 0 and workers > 1 and not _env_truthy("SEAM_API_ALLOW_PROCESS_LOCAL_RATE_LIMIT"):
        raise RuntimeError(
            "SEAM API rate limiting is process-local; use one worker or set "
            "SEAM_API_ALLOW_PROCESS_LOCAL_RATE_LIMIT=1 after placing a shared limiter in front."
        )
    if _is_remote_bind(host) and not os.environ.get("SEAM_API_TOKEN") and not _env_truthy("SEAM_API_ALLOW_REMOTE_NO_TOKEN"):
        raise RuntimeError(
            "Refusing to bind API to a non-loopback host without an authentication token. "
            "Set SEAM_API_TOKEN to enable authenticated remote access, bind to 127.0.0.1, "
            "or set SEAM_API_ALLOW_REMOTE_NO_TOKEN=1 intentionally."
        )
    if os.environ.get("SEAM_API_TOKEN") and _is_remote_bind(host) and not _env_truthy("SEAM_API_ALLOW_INSECURE_REMOTE"):
        raise RuntimeError(
            "Refusing to bind authenticated API to a non-loopback host without TLS. "
            "Use a TLS reverse proxy, bind to 127.0.0.1, or set SEAM_API_ALLOW_INSECURE_REMOTE=1 intentionally."
        )


def _is_remote_bind(host: str) -> bool:
    normalized = host.strip().lower().strip("[]")
    return normalized not in {"127.0.0.1", "::1", "localhost"}


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


# -- tree endpoint helpers ---------------------------------------------------

_TREE_SKIP_NAMES = {"__pycache__", "node_modules", "build", "dist", ".venv", "venv"}


def _tree_root() -> Path:
    raw = os.environ.get("SEAM_API_TREE_ROOT")
    return Path(raw).resolve() if raw else Path.cwd()


def _tree_max_depth() -> int:
    try:
        v = int(os.environ.get("SEAM_API_TREE_MAX_DEPTH", "4"))
    except ValueError:
        v = 4
    return max(0, min(v, 16))


def _tree_max_entries() -> int:
    try:
        v = int(os.environ.get("SEAM_API_TREE_MAX_ENTRIES", "2000"))
    except ValueError:
        v = 2000
    return max(1, min(v, 100000))


def _resolve_tree_path(root: Path, requested: str) -> Path:
    resolved = (root / requested).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("outside root")
    return resolved


def _walk_tree(
    start: Path,
    root: Path,
    *,
    depth: int = 0,
    max_depth: int,
    max_entries: int,
    counter: list[int],
    truncated: list[bool],
) -> list[dict[str, Any]]:
    if truncated[0]:
        return []
    entries: list[dict[str, Any]] = []
    with os.scandir(start) as dir_entries:
        for entry in dir_entries:
                if truncated[0]:
                    break
                if entry.name.startswith(".") and entry.name != ".seam":
                    continue
                if entry.name in _TREE_SKIP_NAMES:
                    continue
                counter[0] += 1
                if counter[0] > max_entries:
                    truncated[0] = True
                    break
                entry_path = Path(entry.path)
                rel_id = entry_path.relative_to(root).as_posix() if entry_path.is_relative_to(root) else entry.path
                if entry.is_dir(follow_symlinks=False):
                    node: dict[str, Any] = {
                        "id": rel_id,
                        "name": entry.name,
                        "type": "folder",
                        "children": [],
                    }
                    if depth < max_depth:
                        try:
                            node["children"] = _walk_tree(
                                entry_path,
                                root,
                                depth=depth + 1,
                                max_depth=max_depth,
                                max_entries=max_entries,
                                counter=counter,
                                truncated=truncated,
                            )
                        except (PermissionError, OSError) as exc:
                            node["error"] = type(exc).__name__
                    entries.append(node)
                else:
                    lang = entry.name.rsplit(".", 1)[-1] if "." in entry.name else ""
                    entries.append({
                        "id": rel_id,
                        "name": entry.name,
                        "type": "file",
                        "lang": lang,
                    })
    return sorted(entries, key=lambda x: (x["type"] != "folder", x["name"].lower()))


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

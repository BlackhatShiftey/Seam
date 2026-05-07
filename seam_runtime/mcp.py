from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import TextIO

from .doctor import build_doctor_report
from .holographic import decode_surface, query_surface
from .runtime import SeamRuntime


# Backwards-compatible name->description map. The ready line still emits this
# under the "tools" key so existing JSONL clients keep working.
TOOL_DESCRIPTIONS = {
    "seam_memory_search": "Return compact progressive-disclosure memory search results.",
    "seam_memory_get": "Return full MIRL records for selected ids.",
    "seam_ingest": "Compile and persist text into SEAM memory.",
    "seam_stats": "Return SQLite store stats (record counts, vector index size, document totals).",
    "seam_documents": "List recent persisted document_status rows (source_ref, hash, indexed state).",
    "seam_context": "Search and pack a prompt-ready context payload for a query (mirrors `seam context`).",
    "seam_doctor": "Run the SEAM install/runtime smoke check (mirrors `seam doctor`); pgvector error strings are redacted.",
    "seam_surface_list": "List stored SEAM-HS/1 surface library entries (mirrors `seam surface list`).",
    "seam_surface_show": "Show one stored SEAM-HS/1 surface library entry by `hs:<id>` ref (mirrors `seam surface show`).",
    "seam_surface_query": "Query embedded MIRL or SEAM-RC/1 directly inside a registered HS/1 surface by `hs:<id>` (mirrors `seam surface query`).",
    "seam_surface_decode": "Decode the embedded payload of a registered HS/1 surface by `hs:<id>` and return its metadata + truncated text view.",
    "seam_benchmark_latest": "Return the most recent persisted benchmark run summaries (mirrors `seam benchmark history`).",
}


# Structured tool metadata: input schema + annotations. Emitted on the ready
# line alongside TOOL_DESCRIPTIONS for clients that want richer info. Per
# MCP best practices, annotations are hints for the agent (not security gates).
TOOL_METADATA = {
    "seam_memory_search": {
        "description": TOOL_DESCRIPTIONS["seam_memory_search"],
        "input_schema": {
            "query": {"type": "string", "required": True, "description": "Search text."},
            "scope": {"type": "string", "required": False, "description": "Optional scope filter (e.g. 'thread', 'project')."},
            "budget": {"type": "integer", "required": False, "default": 5, "description": "Max number of compact index hits."},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_memory_get": {
        "description": TOOL_DESCRIPTIONS["seam_memory_get"],
        "input_schema": {
            "ids": {"type": "array<string> or comma-string", "required": True, "description": "Record ids returned by seam_memory_search."},
            "timeline": {"type": "boolean", "required": False, "default": False, "description": "Include neighbor-event timeline context."},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_ingest": {
        "description": TOOL_DESCRIPTIONS["seam_ingest"],
        "input_schema": {
            "text": {"type": "string", "required": True, "description": "Raw natural-language text to compile + persist."},
            "source_ref": {"type": "string", "required": False, "default": "agent://input", "description": "Stable source identifier for document_status."},
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_stats": {
        "description": TOOL_DESCRIPTIONS["seam_stats"],
        "input_schema": {},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_documents": {
        "description": TOOL_DESCRIPTIONS["seam_documents"],
        "input_schema": {
            "limit": {"type": "integer", "required": False, "default": 20, "minimum": 1, "maximum": 200, "description": "Max number of recent documents to return."},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_context": {
        "description": TOOL_DESCRIPTIONS["seam_context"],
        "input_schema": {
            "query": {"type": "string", "required": True, "description": "Question or topic to retrieve context for."},
            "scope": {"type": "string", "required": False},
            "budget": {"type": "integer", "required": False, "default": 5, "description": "Max search candidates considered."},
            "pack_budget": {"type": "integer", "required": False, "default": 512, "description": "Token budget for the prompt-ready pack."},
            "lens": {"type": "string", "required": False, "default": "rag", "description": "Pack lens label."},
            "mode": {"type": "string", "required": False, "default": "context", "description": "Pack mode: 'context' (default), 'narrative', or 'exact'."},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_doctor": {
        "description": TOOL_DESCRIPTIONS["seam_doctor"],
        "input_schema": {},
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
    "seam_surface_list": {
        "description": TOOL_DESCRIPTIONS["seam_surface_list"],
        "input_schema": {
            "limit": {"type": "integer", "required": False, "default": 20, "minimum": 1, "maximum": 200},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_surface_show": {
        "description": TOOL_DESCRIPTIONS["seam_surface_show"],
        "input_schema": {
            "surface_ref": {"type": "string", "required": True, "pattern": "^hs:[0-9a-f]+$", "description": "Canonical 'hs:<hex>' surface id from seam_surface_list."},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_surface_query": {
        "description": TOOL_DESCRIPTIONS["seam_surface_query"],
        "input_schema": {
            "surface_ref": {"type": "string", "required": True, "pattern": "^hs:[0-9a-f]+$"},
            "query": {"type": "string", "required": True},
            "limit": {"type": "integer", "required": False, "default": 5, "minimum": 1, "maximum": 50},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_surface_decode": {
        "description": TOOL_DESCRIPTIONS["seam_surface_decode"],
        "input_schema": {
            "surface_ref": {"type": "string", "required": True, "pattern": "^hs:[0-9a-f]+$"},
            "truncate_text": {"type": "integer", "required": False, "default": 4096, "minimum": 0, "maximum": 65536, "description": "Max chars of decoded text to return; 0 returns metadata only."},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    "seam_benchmark_latest": {
        "description": TOOL_DESCRIPTIONS["seam_benchmark_latest"],
        "input_schema": {
            "limit": {"type": "integer", "required": False, "default": 1, "minimum": 1, "maximum": 50},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
}


_HS_REF_PATTERN = re.compile(r"^hs:[0-9a-f]+$")


def run_stdio_bridge(runtime: SeamRuntime, input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> None:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    _write(output_stream, {"type": "ready", "tools": TOOL_DESCRIPTIONS, "tool_metadata": TOOL_METADATA})
    for line in input_stream:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = dispatch_tool(runtime, request)
        except Exception as exc:  # pragma: no cover - defensive bridge boundary
            response = {"type": "error", "error": str(exc)}
        _write(output_stream, response)


def dispatch_tool(runtime: SeamRuntime, request: dict[str, object]) -> dict[str, object]:
    name = str(request.get("tool") or request.get("name") or "")
    arguments = request.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    if name == "seam_memory_search":
        query = str(arguments.get("query") or "")
        budget = int(arguments.get("budget") or 5)
        scope = arguments.get("scope")
        return {"type": "result", "tool": name, "result": runtime.memory_search(query, scope=str(scope) if scope else None, budget=budget)}
    if name == "seam_memory_get":
        ids = arguments.get("ids") or arguments.get("record_ids") or []
        if isinstance(ids, str):
            record_ids = [part.strip() for part in ids.split(",") if part.strip()]
        else:
            record_ids = [str(item) for item in ids]
        return {"type": "result", "tool": name, "result": runtime.memory_get(record_ids, include_timeline=bool(arguments.get("timeline")))}
    if name == "seam_ingest":
        text = str(arguments.get("text") or "")
        source_ref = str(arguments.get("source_ref") or "agent://input")
        return {"type": "result", "tool": name, "result": runtime.ingest_text(text, source_ref=source_ref, persist=True).to_dict()}
    if name == "seam_stats":
        return {"type": "result", "tool": name, "result": runtime.store.get_stats()}
    if name == "seam_documents":
        limit = _bounded_int(arguments.get("limit"), default=20, low=1, high=200)
        rows = runtime.store.list_document_status(limit=limit)
        return {"type": "result", "tool": name, "result": _paginated(rows, key="documents", limit=limit)}
    if name == "seam_context":
        query = str(arguments.get("query") or "")
        if not query.strip():
            raise ValueError("query is required for seam_context; pass {arguments:{query:'...'}}")
        scope_arg = arguments.get("scope")
        budget = int(arguments.get("budget") or 5)
        pack_budget = int(arguments.get("pack_budget") or 512)
        lens = str(arguments.get("lens") or "rag")
        mode = str(arguments.get("mode") or "context")
        search_result = runtime.search_ir(
            query=query,
            scope=str(scope_arg) if isinstance(scope_arg, str) and scope_arg else None,
            budget=budget,
            lens=str(arguments.get("search_lens") or "general"),
        )
        record_ids = [candidate.record.id for candidate in search_result.candidates]
        pack = runtime.pack_ir(record_ids=record_ids, lens=lens, budget=pack_budget, mode=mode)
        return {
            "type": "result",
            "tool": name,
            "result": {
                "query": query,
                "candidates": search_result.to_dict()["candidates"],
                "pack": pack.to_dict(),
            },
        }
    if name == "seam_doctor":
        return {"type": "result", "tool": name, "result": _redact_doctor_report(build_doctor_report())}
    if name == "seam_surface_list":
        limit = _bounded_int(arguments.get("limit"), default=20, low=1, high=200)
        rows = runtime.store.list_surface_artifacts(limit=limit)
        return {"type": "result", "tool": name, "result": _paginated(rows, key="surfaces", limit=limit)}
    if name == "seam_surface_show":
        surface_ref = _validated_hs_ref(arguments.get("surface_ref") or arguments.get("ref"))
        try:
            row = runtime.store.read_surface_artifact(surface_ref)
        except KeyError:
            raise KeyError(f"No registered surface for ref '{surface_ref}'. Use seam_surface_list to discover registered surfaces.")
        return {"type": "result", "tool": name, "result": row}
    if name == "seam_surface_query":
        surface_ref = _validated_hs_ref(arguments.get("surface_ref") or arguments.get("ref"))
        query = str(arguments.get("query") or "")
        if not query.strip():
            raise ValueError("query is required for seam_surface_query")
        limit = _bounded_int(arguments.get("limit"), default=5, low=1, high=50)
        artifact_path = _resolve_registered_surface_path(runtime, surface_ref)
        result = query_surface(artifact_path, query=query, limit=limit)
        return {"type": "result", "tool": name, "result": result.to_dict()}
    if name == "seam_surface_decode":
        surface_ref = _validated_hs_ref(arguments.get("surface_ref") or arguments.get("ref"))
        truncate_text = _bounded_int(arguments.get("truncate_text"), default=4096, low=0, high=65536)
        artifact_path = _resolve_registered_surface_path(runtime, surface_ref)
        payload = decode_surface(artifact_path)
        result = payload.to_dict(include_payload=False)
        if truncate_text > 0 and payload.payload_format in {"MIRL", "SEAM-RC/1", "SEAM-RC\1"}:
            text = payload.text
            result["payload_text"] = text[:truncate_text]
            result["payload_text_truncated"] = len(text) > truncate_text
        else:
            result["payload_text"] = None
            result["payload_text_truncated"] = False
        return {"type": "result", "tool": name, "result": result}
    if name == "seam_benchmark_latest":
        limit = _bounded_int(arguments.get("limit"), default=1, low=1, high=50)
        rows = runtime.list_benchmark_runs(limit=limit)
        return {"type": "result", "tool": name, "result": _paginated(rows, key="runs", limit=limit)}
    raise ValueError(
        f"Unknown SEAM MCP tool: {name!r}. Known tools: {sorted(TOOL_DESCRIPTIONS)}."
    )


def _bounded_int(value: object, *, default: int, low: int, high: int) -> int:
    if value is None or value == "":
        return default
    try:
        coerced = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected integer in [{low}, {high}], got {value!r}") from exc
    return max(low, min(coerced, high))


def _paginated(rows: list[dict[str, object]], *, key: str, limit: int) -> dict[str, object]:
    return {
        key: rows,
        "count": len(rows),
        "limit": limit,
        "has_more": len(rows) >= limit,
    }


def _validated_hs_ref(value: object) -> str:
    ref = str(value or "").strip()
    if not ref:
        raise ValueError("surface_ref is required; canonical form is 'hs:<hex>' (use seam_surface_list to discover refs).")
    if not _HS_REF_PATTERN.match(ref):
        raise ValueError(
            f"Invalid surface_ref {ref!r}; canonical form is 'hs:<hex>'. "
            "MCP tools only accept canonical ids — file paths are rejected. Use seam_surface_list to discover registered surfaces."
        )
    return ref


def _resolve_registered_surface_path(runtime: SeamRuntime, surface_ref: str) -> Path:
    try:
        row = runtime.store.read_surface_artifact(surface_ref)
    except KeyError:
        raise KeyError(f"No registered surface for ref '{surface_ref}'. Use seam_surface_list to discover registered surfaces.")
    artifact_path = Path(str(row.get("artifact_path") or ""))
    if not artifact_path or not artifact_path.exists():
        raise FileNotFoundError(
            f"Surface '{surface_ref}' is registered but its artifact file is missing or unreadable. "
            "Use the SEAM CLI 'seam surface repair <ref>' to restore the redundant copy from source."
        )
    return artifact_path


def _redact_doctor_report(report: dict[str, object]) -> dict[str, object]:
    safe = dict(report)
    pgvector = safe.get("pgvector")
    if isinstance(pgvector, dict) and "error" in pgvector:
        scrubbed = {key: value for key, value in pgvector.items() if key != "error"}
        scrubbed["error_redacted"] = True
        safe["pgvector"] = scrubbed
    return safe


def _write(output_stream: TextIO, payload: dict[str, object]) -> None:
    output_stream.write(json.dumps(payload, sort_keys=True) + "\n")
    output_stream.flush()

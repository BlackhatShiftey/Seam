from __future__ import annotations

import json
import sys
from typing import TextIO

from .runtime import SeamRuntime


TOOL_DESCRIPTIONS = {
    "seam_memory_search": "Return compact progressive-disclosure memory search results.",
    "seam_memory_get": "Return full MIRL records for selected ids.",
    "seam_ingest": "Compile and persist text into SEAM memory.",
}


def run_stdio_bridge(runtime: SeamRuntime, input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> None:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    _write(output_stream, {"type": "ready", "tools": TOOL_DESCRIPTIONS})
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
    raise ValueError(f"Unknown SEAM MCP tool: {name}")


def _write(output_stream: TextIO, payload: dict[str, object]) -> None:
    output_stream.write(json.dumps(payload, sort_keys=True) + "\n")
    output_stream.flush()

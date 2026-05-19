"""Context pack persistence must be explicit.

Context retrieval is an agent-facing read path. It should not mutate SQLite
with generated PACK records unless the caller opts in.
"""

from fastapi.testclient import TestClient

from seam_runtime.mcp import TOOL_METADATA, dispatch_tool
from seam_runtime.mirl import RecordKind
from seam_runtime.runtime import SeamRuntime
from seam_runtime.server import create_app


def _seed_runtime(runtime: SeamRuntime) -> list[str]:
    batch = runtime.compile_nl(
        "SEAM stores durable memory for prompt-ready context retrieval.",
        source_ref="unit://context-pack-policy",
    )
    runtime.persist_ir(batch)
    return [record.id for record in batch.records]


def _pack_ids(runtime: SeamRuntime) -> list[str]:
    return [record.id for record in runtime.store.load_ir().records if record.kind == RecordKind.PACK]


def test_runtime_pack_ir_does_not_persist_pack_by_default(tmp_path):
    runtime = SeamRuntime(tmp_path / "seam.db")
    record_ids = _seed_runtime(runtime)

    runtime.pack_ir(record_ids=record_ids, mode="context")

    assert _pack_ids(runtime) == []


def test_runtime_pack_ir_persists_pack_when_requested(tmp_path):
    runtime = SeamRuntime(tmp_path / "seam.db")
    record_ids = _seed_runtime(runtime)

    runtime.pack_ir(record_ids=record_ids, mode="context", persist=True)

    assert _pack_ids(runtime)


def test_rest_context_does_not_persist_pack_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("SEAM_API_RATE_LIMIT_PER_MINUTE", "0")
    runtime = SeamRuntime(tmp_path / "seam.db")
    _seed_runtime(runtime)
    client = TestClient(create_app(runtime))

    response = client.post("/context", json={"query": "prompt-ready context"})

    assert response.status_code == 200
    assert _pack_ids(runtime) == []


def test_mcp_context_does_not_persist_pack_by_default(tmp_path):
    runtime = SeamRuntime(tmp_path / "seam.db")
    _seed_runtime(runtime)

    dispatch_tool(
        runtime,
        {"tool": "seam_context", "arguments": {"query": "prompt-ready context"}},
    )

    assert _pack_ids(runtime) == []


def test_mcp_context_tool_contract_has_no_persist_argument():
    metadata = TOOL_METADATA["seam_context"]

    assert metadata["annotations"]["readOnlyHint"] is True
    assert "persist" not in metadata["input_schema"]

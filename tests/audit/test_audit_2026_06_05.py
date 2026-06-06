"""Regression guards for the 2026-06-05 correctness/security audit fixes.

Each test fails against the pre-fix code and passes after. Covers:
  AUD-02/03  graph adapter namespace + scoped-edge isolation
  AUD-04     mode="vector" must not inject the sql leg
  AUD-05     /chat base_url SSRF guard (private/link-local rejected, loopback allowed)
  AUD-06     PNG image-bomb / oversized-dimension guard
  AUD-07     readable decompression raises ValueError (not KeyError) on a corrupt order
  AUD-08     shell validation rejects a path in argv[0]
"""
import json
import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from seam_runtime.dashboard import _validate_shell_command
from seam_runtime.holographic import (
    MAX_SURFACE_DIMENSION,
    PNG_SIGNATURE,
    _bounded_inflate,
    _png_chunk,
    _read_png,
)
from seam_runtime.lossless import compress_text_readable, decompress_text_readable
from seam_runtime.retrieval_orchestrator import RetrievalOrchestrator
from seam_runtime.retrieval_orchestrator.planner import build_plan
from seam_runtime.runtime import SeamRuntime
from seam_runtime.server import create_app_from_env


# --------------------------------------------------------------------------- #
# AUD-08 — shell validation: a path in argv[0] must not pass via its basename
# --------------------------------------------------------------------------- #
class TestShellPathBypass:
    def test_absolute_path_basename_bypass_rejected(self):
        with pytest.raises(PermissionError):
            _validate_shell_command("/custom/path/git status")

    def test_relative_path_basename_bypass_rejected(self):
        with pytest.raises(PermissionError):
            _validate_shell_command("./git status")

    def test_slash_in_later_arg_still_allowed(self):
        assert _validate_shell_command("ls /tmp") == ["ls", "/tmp"]
        assert _validate_shell_command("cat /etc/hosts") == ["cat", "/etc/hosts"]


# --------------------------------------------------------------------------- #
# AUD-07 — readable decompression: corrupt order -> ValueError, not KeyError
# --------------------------------------------------------------------------- #
class TestReadableDecompressCorruptOrder:
    def test_missing_chunk_in_order_raises_valueerror(self):
        artifact = compress_text_readable("The quick brown fox. The quick brown fox jumps.")
        machine_text = artifact.machine_text
        lines = machine_text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("ORDER|"):
                payload = json.loads(line[len("ORDER|"):])
                payload["items"][0]["id"] = "c:nonexistent"
                lines[i] = "ORDER|" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                break
        corrupt = "\n".join(lines)
        with pytest.raises(ValueError):
            decompress_text_readable(corrupt)


# --------------------------------------------------------------------------- #
# AUD-04 — mode="vector" must not inject the sql leg
# --------------------------------------------------------------------------- #
class TestVectorModeNoSqlLeg:
    def test_vector_mode_filtered_query_has_no_sql_leg(self):
        plan = build_plan("kind:CLM", mode="vector")
        names = [leg.name for leg in plan.legs]
        assert "sql" not in names
        assert names == ["vector"]

    def test_hybrid_mode_still_has_sql_leg(self):
        plan = build_plan("kind:CLM ledger", mode="hybrid")
        assert "sql" in [leg.name for leg in plan.legs]

    def test_structured_intent_still_runs_sql_outside_vector_mode(self):
        # A pure-filter query in hybrid mode keeps the sql leg.
        plan = build_plan("kind:CLM", mode="hybrid")
        assert "sql" in [leg.name for leg in plan.legs]


# --------------------------------------------------------------------------- #
# AUD-06 — PNG image bomb / oversized dimensions
# --------------------------------------------------------------------------- #
def _make_png(width: int, height: int, raw: bytes, color_type: int = 6, bit_depth: int = 8) -> bytes:
    png = bytearray(PNG_SIGNATURE)
    png.extend(_png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)))
    png.extend(_png_chunk(b"IDAT", zlib.compress(raw)))
    png.extend(_png_chunk(b"IEND", b""))
    return bytes(png)


class TestPngBombGuard:
    def test_bounded_inflate_rejects_overrun(self):
        data = zlib.compress(b"x" * 1000)
        with pytest.raises(ValueError):
            _bounded_inflate(data, 10)
        assert _bounded_inflate(data, 1000) == b"x" * 1000

    def test_read_png_rejects_oversized_dimensions(self, tmp_path):
        p = tmp_path / "huge.png"
        p.write_bytes(_make_png(MAX_SURFACE_DIMENSION + 1, 1, b"\x00" * 16))
        with pytest.raises(ValueError):
            _read_png(p)

    def test_read_png_rejects_decompression_bomb(self, tmp_path):
        # Declare tiny dimensions (expected_raw is small) but ship an IDAT that
        # inflates far beyond it — the bounded inflate must reject it.
        p = tmp_path / "bomb.png"
        p.write_bytes(_make_png(2, 2, b"\x00" * (1024 * 1024)))
        with pytest.raises(ValueError):
            _read_png(p)


# --------------------------------------------------------------------------- #
# AUD-05 — /chat base_url SSRF guard
# --------------------------------------------------------------------------- #
class TestChatBaseUrlSsrf:
    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SEAM_SERVER_DB", str(tmp_path / "ssrf.db"))
        monkeypatch.delenv("SEAM_API_TOKEN", raising=False)
        monkeypatch.delenv("SEAM_PGVECTOR_DSN", raising=False)
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
            monkeypatch.delenv(key, raising=False)

    def _client(self):
        return TestClient(create_app_from_env())

    def test_link_local_metadata_address_rejected(self):
        resp = self._client().post("/chat", json={
            "message": "hi", "model": "x", "provider": "OpenAI",
            "base_url": "http://169.254.169.254/latest/meta-data", "api_key": "k",
        })
        assert resp.status_code == 400
        assert "disallowed" in resp.json()["detail"].lower()

    def test_private_range_rejected(self):
        resp = self._client().post("/chat", json={
            "message": "hi", "model": "x", "provider": "OpenAI",
            "base_url": "http://10.0.0.5:8080/v1", "api_key": "k",
        })
        assert resp.status_code == 400

    def test_non_http_scheme_rejected(self):
        resp = self._client().post("/chat", json={
            "message": "hi", "model": "x", "provider": "OpenAI",
            "base_url": "file:///etc/passwd", "api_key": "k",
        })
        assert resp.status_code == 400
        assert "scheme" in resp.json()["detail"].lower()

    def test_loopback_allowed_reaches_provider_call(self):
        # Loopback is allowed by design (Ollama). The SSRF guard must pass it
        # through to the provider call, which fails with 502 (nothing listening),
        # not a 400 validation error.
        resp = self._client().post("/chat", json={
            "message": "hi", "model": "x", "provider": "ollama",
            "base_url": "http://127.0.0.1:11434/v1",
        })
        assert resp.status_code == 502


# --------------------------------------------------------------------------- #
# AUD-02 / AUD-03 — graph adapter namespace + scoped-edge isolation
# --------------------------------------------------------------------------- #
class TestGraphAdapterIsolation:
    def test_graph_leg_returns_only_in_scope_records(self, tmp_path):
        rt = SeamRuntime(str(tmp_path / "graph.db"))
        rt.persist_ir(rt.compile_nl("Alice manages the alpha payment ledger.", ns="alpha", scope="project"))
        rt.persist_ir(rt.compile_nl("Carol runs the beta payment ledger.", ns="beta", scope="thread"))
        orch = RetrievalOrchestrator(rt)
        plan = orch.plan("payment ledger", scope="project", mode="graph")
        hits = orch.graph_adapter.search(plan, limit=10)
        assert hits  # the in-scope record is found
        for hit in hits:
            assert hit.record.scope == "project"

    def test_graph_leg_respects_namespace_filter(self, tmp_path):
        rt = SeamRuntime(str(tmp_path / "graph_ns.db"))
        rt.persist_ir(rt.compile_nl("Alice manages the alpha payment ledger.", ns="alpha", scope="project"))
        rt.persist_ir(rt.compile_nl("Bob runs the beta payment ledger.", ns="beta", scope="project"))
        orch = RetrievalOrchestrator(rt)
        plan = orch.plan("ns:alpha payment ledger", scope="project", mode="graph")
        hits = orch.graph_adapter.search(plan, limit=10)
        for hit in hits:
            assert hit.record.ns == "alpha"

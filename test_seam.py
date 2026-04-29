import json
import os
import tempfile
import asyncio
import unittest
from contextlib import redirect_stdout
from importlib.util import find_spec
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from experimental.retrieval_orchestrator import ChromaSemanticAdapter, QueryIntent, RetrievalOrchestrator
from experimental.retrieval_orchestrator.adapters import SQLiteIRAdapter
from experimental.retrieval_orchestrator.planner import build_plan
from seam import SeamRuntime, compile_dsl, compile_nl, decompile_ir, load_ir_lines, pack_ir, render_ir, unpack_pack
from seam_runtime import benchmarks as benchmark_module
from seam_runtime.cli import run_cli
from seam_runtime.dashboard import DEFAULT_CHAT_MODELS, SeamChatClient, TextualDashboardApp, run_dashboard
from seam_runtime.installer import (
    InstallLayout,
    PATH_MARKER_BEGIN,
    _ensure_posix_shell_profiles,
    default_runtime_db_path,
    detect_layout,
    install_repo,
    path_in_environment,
    render_posix_shim,
    render_windows_cmd_shim,
    write_shims,
)
from seam_runtime.lossless import (
    benchmark_text_lossless,
    compress_text_lossless,
    compress_text_readable,
    decompress_text_lossless,
    decompress_text_readable,
    query_readable_compressed,
)
from seam_runtime.models import (
    HashEmbeddingModel,
    OpenAICompatibleEmbeddingModel,
    cosine,
    default_embedding_model,
)
from seam_runtime.mcp import dispatch_tool
from seam_runtime.pack import score_pack, unpack_exact_pack
from seam_runtime.symbols import build_symbol_maps, namespace_chain
from seam_runtime.ui.animations import AnimationEngine
from seam_runtime.vector import INDEXABLE_KINDS
from seam_runtime.vector_adapters import PgVectorAdapter
from seam_runtime.verify import verify_ir

try:
    from rich.console import Console
except ImportError:  # pragma: no cover - optional at import time
    Console = None

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - optional server extra
    TestClient = None


class SeamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path(f"test_seam_{uuid4().hex}.db")

    def tearDown(self) -> None:
        try:
            if self.db_path.exists():
                self.db_path.unlink()
        except PermissionError:
            pass

    def test_compile_generates_core_records(self) -> None:
        text = (
            "We want to design a language for AI that permanently remembers things. "
            "It should work for databases, RAG pipelines, and context windows. "
            "The goal is to compress information to the simplest form possible without losing meaning."
        )
        records = compile_nl(text)
        ir = render_ir(records)
        self.assertIn("ENT|ent:project:seam|", ir)
        self.assertIn("CLM|clm:1|", ir)
        self.assertIn('"object":["db","rag","ctx"]', ir)
        self.assertIn('"simplest_recoverable_form"', ir)

    def test_exact_pack_round_trips(self) -> None:
        text = "Build durable AI memory for databases and context windows without losing meaning."
        batch = compile_nl(text)
        pack = pack_ir(batch, lens="design", mode="exact")
        unpacked = unpack_exact_pack(pack)
        self.assertEqual(batch.to_json(), unpacked.to_json())

    def test_verifier_rejects_missing_claim_fields(self) -> None:
        batch = compile_dsl(
            """
entity project "SEAM" as p1
claim c1:
  subject p1
"""
        )
        report = verify_ir(batch)
        self.assertFalse(report.valid)
        self.assertTrue(any(issue.code == "missing_claim_field" for issue in report.issues))

    def test_runtime_persist_search_trace(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_nl(
            "We want a universal AI memory language for databases, RAG pipelines, and context windows. "
            "It should translate back into natural language without losing meaning."
        )
        runtime.persist_ir(batch)
        result = runtime.search_ir("translator natural language", budget=3)
        self.assertTrue(result.candidates)
        trace = runtime.trace("clm:5")
        node_ids = {node.id for node in trace.nodes}
        self.assertIn("prov:compile:1", node_ids)
        self.assertIn("span:1", node_ids)

    @unittest.skipIf(TestClient is None, "fastapi server extra is not installed")
    def test_rest_api_compile_search_context_stats_and_auth(self) -> None:
        from seam_runtime.server import create_app

        runtime = SeamRuntime(self.db_path)
        with patch.dict(os.environ, {"SEAM_API_TOKEN": "test-token"}, clear=False):
            client = TestClient(create_app(runtime))

        self.assertEqual(client.get("/health").json()["status"], "ok")
        self.assertEqual(client.get("/stats").status_code, 401)

        headers = {"Authorization": "Bearer test-token"}
        compile_response = client.post(
            "/compile",
            json={"text": "SEAM stores durable memory for agent retrieval.", "persist": True},
            headers=headers,
        )
        self.assertEqual(compile_response.status_code, 200)
        self.assertTrue(compile_response.json()["records"])
        self.assertTrue(compile_response.json()["persist"]["stored_ids"])

        search_response = client.get("/search", params={"query": "durable memory", "budget": 3}, headers=headers)
        self.assertEqual(search_response.status_code, 200)
        self.assertTrue(search_response.json()["candidates"])

        context_response = client.post("/context", json={"query": "agent retrieval", "budget": 3}, headers=headers)
        self.assertEqual(context_response.status_code, 200)
        self.assertIn("pack", context_response.json())

        stats_response = client.get("/stats", headers=headers)
        self.assertEqual(stats_response.status_code, 200)
        self.assertGreater(stats_response.json()["total_records"], 0)

    @unittest.skipIf(TestClient is None, "fastapi server extra is not installed")
    def test_rest_api_rate_limits_health_and_protected_endpoints(self) -> None:
        from seam_runtime.server import create_app

        runtime = SeamRuntime(self.db_path)
        with patch.dict(os.environ, {"SEAM_API_TOKEN": "test-token", "SEAM_API_RATE_LIMIT_PER_MINUTE": "1"}, clear=False):
            client = TestClient(create_app(runtime))

        first = client.get("/health")
        second = client.get("/health")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

        headers = {"Authorization": "Bearer another-test-token"}
        limited = client.get("/stats", headers=headers)
        self.assertEqual(limited.status_code, 401)

    def test_vector_index_reindex_and_search(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_nl("We need a translator back into natural language for memory workflows.")
        runtime.store.persist_ir(batch)
        reindex_report = runtime.reindex_vectors()
        self.assertIn("clm:2", reindex_report["indexed_ids"])
        self.assertTrue(reindex_report["stale_before"])
        second_reindex = runtime.reindex_vectors()
        self.assertEqual(second_reindex["stale_before"], [])
        result = runtime.search_ir("translator natural language", budget=3)
        top_ids = [candidate.record.id for candidate in result.candidates]
        self.assertIn("clm:2", top_ids)

    def test_ingest_persists_document_status_and_memory_search_get(self) -> None:
        runtime = SeamRuntime(self.db_path)
        report = runtime.ingest_text(
            "SEAM gives agents persistent local memory with graph and vector retrieval.",
            source_ref="unit://competitive-plan",
            persist=True,
        )
        payload = report.to_dict()
        self.assertEqual(payload["document"]["extraction_status"], "compiled")
        self.assertEqual(payload["document"]["indexed_status"], "indexed")
        self.assertTrue(payload["stored_ids"])

        listed = runtime.store.list_document_status()
        self.assertEqual(listed[0]["source_ref"], "unit://competitive-plan")
        index = runtime.memory_search("persistent local memory", budget=3)
        self.assertTrue(index["results"])
        full = runtime.memory_get([index["results"][0]["id"]], include_timeline=True)
        self.assertTrue(full["records"])
        self.assertIn("context", full)

    def test_retrieval_modes_include_vector_graph_hybrid_mix(self) -> None:
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("SEAM stores graph edges and vector embeddings for agent memory retrieval."))
        orchestrator = RetrievalOrchestrator(runtime)
        for mode in ("vector", "graph", "hybrid", "mix"):
            result = orchestrator.search("agent memory retrieval", budget=3, mode=mode, include_trace=True).to_dict()
            self.assertEqual(result["trace"]["plan"]["mode"], mode)
            self.assertTrue(result["trace"]["plan"]["legs"])
        mix_legs = [leg["name"] for leg in orchestrator.plan("agent memory retrieval", mode="mix").to_dict()["legs"]]
        self.assertEqual(mix_legs, ["sql", "vector", "graph"])

    def test_mcp_bridge_dispatches_memory_tools(self) -> None:
        runtime = SeamRuntime(self.db_path)
        ingest = dispatch_tool(
            runtime,
            {
                "tool": "seam_ingest",
                "arguments": {"text": "SEAM MCP exposes persistent memory search.", "source_ref": "unit://mcp"},
            },
        )
        self.assertEqual(ingest["type"], "result")
        search = dispatch_tool(runtime, {"tool": "seam_memory_search", "arguments": {"query": "persistent memory"}})
        self.assertTrue(search["result"]["results"])
        record_id = search["result"]["results"][0]["id"]
        full = dispatch_tool(runtime, {"tool": "seam_memory_get", "arguments": {"ids": [record_id], "timeline": True}})
        self.assertTrue(full["result"]["records"])

    def test_symbol_promotion_and_pack_compaction(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_nl(
            "We need durable memory. This memory runtime should preserve memory context. "
            "The memory system should improve memory retrieval."
        )
        runtime.persist_ir(batch)
        promote = runtime.promote_symbols(min_frequency=1)
        self.assertTrue(promote.stored_ids)
        compact_batch = runtime.store.load_ir()
        expansion_to_symbol, _ = build_symbol_maps(compact_batch.records, namespace="local.default")
        self.assertEqual(expansion_to_symbol.get("memory"), "mem")
        pack = runtime.pack_ir(
            record_ids=[record.id for record in compact_batch.records if record.kind.value in {"CLM", "STA", "SYM"}],
            mode="context",
        )
        self.assertIn("symbols", pack.payload)
        self.assertTrue(pack.payload["symbols"])
        self.assertIn("mem", pack.payload["symbols"])

    def test_symbol_export_and_query_expansion(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_dsl(
            """
entity project "SEAM" as p1
claim c1:
  subject p1
  predicate memory_runtime
  object memory_runtime
"""
        )
        runtime.persist_ir(batch)
        runtime.promote_symbols(min_frequency=1)
        exported = runtime.export_symbols()
        self.assertIn("SEAM Symbol Nursery", exported)
        all_records = runtime.store.load_ir().records
        symbol_records = [record for record in all_records if record.kind.value == "SYM"]
        self.assertTrue(symbol_records)
        symbol = symbol_records[0].attrs["symbol"]
        result = runtime.search_ir(symbol, budget=5)
        self.assertTrue(result.candidates)

    def test_namespace_chain_inheritance(self) -> None:
        self.assertEqual(namespace_chain("org.app.user.thread"), ["org", "org.app", "org.app.user", "org.app.user.thread"])

    def test_decompile_and_pack_payload(self) -> None:
        batch = compile_nl("We need a translator back into natural language for AI memory.")
        output = decompile_ir(batch, mode="expanded")
        self.assertIn("MIRL summary", output)
        pack = pack_ir(batch, mode="context")
        payload = unpack_pack(pack)
        self.assertIn("entries", payload)

    def test_cli_text_parser_compat(self) -> None:
        batch = compile_nl("Build durable AI memory for databases.")
        parsed = load_ir_lines(batch.to_text())
        self.assertEqual(len(parsed), len(batch.records))

    def test_default_embedding_model_from_env(self) -> None:
        keys = [
            "SEAM_EMBEDDING_PROVIDER",
            "SEAM_EMBEDDING_MODEL",
            "SEAM_EMBEDDING_BASE_URL",
            "SEAM_EMBEDDING_API_KEY_ENV",
            "SEAM_EMBEDDING_TIMEOUT_S",
            "SEAM_EMBEDDING_DIMENSIONS",
        ]
        snapshot = {key: os.environ.get(key) for key in keys}
        try:
            os.environ["SEAM_EMBEDDING_PROVIDER"] = "openai-compatible"
            os.environ["SEAM_EMBEDDING_MODEL"] = "text-embedding-3-small"
            os.environ["SEAM_EMBEDDING_BASE_URL"] = "https://example.test/v1/embeddings"
            os.environ["SEAM_EMBEDDING_API_KEY_ENV"] = "ALT_OPENAI_KEY"
            os.environ["SEAM_EMBEDDING_TIMEOUT_S"] = "12.5"
            os.environ["SEAM_EMBEDDING_DIMENSIONS"] = "256"
            model = default_embedding_model()
        finally:
            for key, value in snapshot.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertIsInstance(model, OpenAICompatibleEmbeddingModel)
        self.assertEqual(model.model, "text-embedding-3-small")
        self.assertEqual(model.base_url, "https://example.test/v1/embeddings")
        self.assertEqual(model.api_key_env, "ALT_OPENAI_KEY")
        self.assertEqual(model.timeout_s, 12.5)
        self.assertEqual(model.dimensions, 256)

    def test_retrieval_benchmark_uses_gold_fixtures(self) -> None:
        runtime = SeamRuntime(self.db_path)
        benchmark = runtime.run_retrieval_benchmark()
        self.assertGreaterEqual(benchmark["summary"]["fixture_count"], 3)
        self.assertIn("hybrid", benchmark["summary"]["tracks"])
        self.assertTrue(benchmark["summary"]["success_checks"]["exact_packs_reversible"])
        categories = {fixture["category"] for fixture in benchmark["fixtures"]}
        self.assertIn("relation", categories)

    def test_pack_scoring_preserves_traceability_metrics(self) -> None:
        batch = compile_nl("We need a translator back into natural language for AI memory.")
        exact = pack_ir(batch, mode="exact")
        context = pack_ir(batch, mode="context")
        exact_score = score_pack(exact, batch.records)
        context_score = score_pack(context, batch.records)
        self.assertEqual(exact_score["reversibility"], 1.0)
        self.assertGreaterEqual(context_score["traceability"], 0.66)
        self.assertGreater(context_score["overall"], 0.0)

    def test_retrieval_orchestrator_builds_mixed_plan(self) -> None:
        runtime = SeamRuntime(self.db_path)
        orchestrator = RetrievalOrchestrator(runtime)
        plan = orchestrator.plan("kind:CLM translator natural language", scope="thread", budget=3)
        self.assertEqual(plan.intent, QueryIntent.HYBRID)
        self.assertEqual(plan.filters.kinds, ["CLM"])
        self.assertEqual([leg.name for leg in plan.legs], ["sql", "vector"])
        self.assertEqual(plan.normalized_query, "translator natural language")

    def test_retrieval_orchestrator_merges_sql_and_vector_legs(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_nl("We need a translator back into natural language for memory workflows.")
        runtime.persist_ir(batch)
        orchestrator = RetrievalOrchestrator(runtime)
        result = orchestrator.search("kind:CLM translator natural language", budget=3, include_trace=True)
        self.assertTrue(result.candidates)
        translator = next((candidate for candidate in result.candidates if candidate.record.id == "clm:2"), None)
        self.assertIsNotNone(translator)
        self.assertIn("sql", translator.sources)
        self.assertIsNotNone(result.trace)
        self.assertIn("sql", result.trace["legs"])
        self.assertIn("vector", result.trace["legs"])

    def test_sql_leg_excludes_irrelevant_kind_only_matches(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_dsl(
            """
entity project "SEAM" as p1
claim c1:
  subject p1
  predicate translator_for
  object natural_language
claim c2:
  subject p1
  predicate memory_runtime
  object durable_context
"""
        )
        runtime.persist_ir(batch)
        adapter = SQLiteIRAdapter(runtime.store)
        hits = adapter.search(build_plan("kind:CLM translator natural language", budget=5), limit=5)
        hit_ids = [hit.record.id for hit in hits]
        self.assertIn("c1", hit_ids)
        self.assertNotIn("c2", hit_ids)

    def test_sql_leg_returns_exact_structured_match_without_query_terms(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_dsl(
            """
entity project "SEAM" as p1
claim c1:
  subject p1
  predicate memory_runtime
  object durable_context
claim c2:
  subject p1
  predicate retrieval_mode
  object vector_search
"""
        )
        runtime.persist_ir(batch)
        adapter = SQLiteIRAdapter(runtime.store)
        hits = adapter.search(build_plan("predicate:memory_runtime subject:p1", budget=5), limit=5)
        self.assertTrue(hits)
        self.assertEqual([hit.record.id for hit in hits], ["c1"])
        self.assertTrue(any(reason == "matched=predicate" for reason in hits[0].reasons))

    def test_cli_plan_outputs_mixed_intent(self) -> None:
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["--db", str(self.db_path), "plan", "kind:CLM translator natural language", "--budget", "3", "--format", "json"])
        payload = stream.getvalue()
        self.assertIn('"intent": "hybrid"', payload)
        self.assertIn('"name": "sql"', payload)
        self.assertIn('"name": "vector"', payload)

    def test_cli_compare_outputs_basic_and_retrieval(self) -> None:
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["--db", str(self.db_path), "compare", "translator natural language", "--budget", "3", "--format", "json"])
        payload = stream.getvalue()
        self.assertIn('"search"', payload)
        self.assertIn('"retrieve"', payload)

    def test_cli_retrieve_pretty_output(self) -> None:
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["--db", str(self.db_path), "retrieve", "kind:CLM translator natural language", "--budget", "3"])
        payload = stream.getvalue()
        self.assertIn("Intent: hybrid", payload)
        self.assertIn("Candidates:", payload)
        self.assertIn("clm:2", payload)

    def test_chroma_semantic_adapter_searches_via_fake_client(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_nl("We need a translator back into natural language for memory workflows.")
        runtime.persist_ir(batch)
        adapter = ChromaSemanticAdapter(runtime.store, runtime.embedding_model, client=FakeChromaClient())
        plan = build_plan("translator natural language", budget=3)
        hits = adapter.search(plan, limit=3)
        self.assertTrue(hits)
        self.assertEqual(hits[0].record.id, "clm:2")
        self.assertEqual(hits[0].leg, "chroma")

    def test_retrieval_orchestrator_syncs_persistent_indexes(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_nl("We need a translator back into natural language for memory workflows.")
        runtime.persist_ir(batch)
        orchestrator = RetrievalOrchestrator(
            runtime,
            semantic_adapter=ChromaSemanticAdapter(runtime.store, runtime.embedding_model, client=FakeChromaClient()),
            semantic_backend="chroma",
        )
        report = orchestrator.sync_persistent_indexes()
        self.assertEqual(report["backend"], "chroma")
        self.assertGreaterEqual(report["chroma_indexed"], 1)
        self.assertIn("clm:2", report["sqlite_indexed"])

    def test_context_pipeline_returns_context_pack(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_nl("We need a translator back into natural language for memory workflows.")
        runtime.persist_ir(batch)
        orchestrator = RetrievalOrchestrator(runtime)
        rag = orchestrator.rag("translator natural language", budget=3, pack_budget=10, include_trace=True)
        self.assertIn("clm:2", rag.candidate_ids)
        self.assertTrue(rag.records)
        self.assertTrue(rag.candidates)
        self.assertEqual(rag.pack["mode"], "context")
        self.assertTrue(rag.pack["payload"]["entries"])
        self.assertIsNotNone(rag.trace)

    def test_cli_rag_search_json_contains_pack(self) -> None:
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["--db", str(self.db_path), "context", "translator natural language", "--budget", "3", "--format", "json"])
        payload = stream.getvalue()
        self.assertIn('"pack"', payload)
        self.assertIn('"candidate_ids"', payload)
        self.assertIn('"records"', payload)

    def test_cli_context_prompt_view_outputs_prompt_ready_text(self) -> None:
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["--db", str(self.db_path), "context", "translator natural language", "--budget", "3", "--view", "prompt"])
        payload = stream.getvalue()
        self.assertIn("SEAM retrieved context", payload)
        self.assertIn("[1] clm:2 [CLM]", payload)

    def test_cli_context_evidence_view_json_contains_citations(self) -> None:
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(
                ["--db", str(self.db_path), "context", "translator natural language", "--budget", "3", "--view", "evidence", "--format", "json"]
            )
        payload = stream.getvalue()
        self.assertIn('"view": "evidence"', payload)
        self.assertIn('"citation"', payload)

    def test_cli_context_records_view_outputs_exact_record_payloads(self) -> None:
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["--db", str(self.db_path), "context", "translator natural language", "--budget", "3", "--view", "records"])
        payload = stream.getvalue()
        self.assertIn('"id": "clm:2"', payload)
        self.assertIn('"kind": "CLM"', payload)

    def test_cli_context_summary_view_reports_highlights(self) -> None:
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["--db", str(self.db_path), "context", "translator natural language", "--budget", "3", "--view", "summary"])
        payload = stream.getvalue()
        self.assertIn("Summary:", payload)
        self.assertIn("Records:", payload)

    def test_lossless_codec_roundtrips_exact_text(self) -> None:
        text = "SEAM preserves exact context while compressing token usage for lossless recovery.\n" * 12
        artifact = compress_text_lossless(text)
        restored = decompress_text_lossless(artifact.machine_text)
        self.assertEqual(restored, text)
        self.assertTrue(artifact.machine_text.startswith("SEAM-LX/1"))

    def test_lossless_benchmark_passes_high_savings_demo(self) -> None:
        text = "\n".join(["SEAM preserves exact context while compressing token usage for lossless recovery."] * 60)
        result = benchmark_text_lossless(text, min_token_savings=0.75)
        self.assertTrue(result.roundtrip_match)
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.artifact.token_savings_ratio, 0.75)
        self.assertTrue(result.search_log)
        self.assertTrue(any(attempt.status == "improved" for attempt in result.search_log))
        self.assertTrue(result.stop_reason)

    def test_lossless_benchmark_logs_fluctuations_for_debugging(self) -> None:
        text = "SEAM preserves exact context while compressing token usage for lossless recovery.\n" * 12
        result = benchmark_text_lossless(text, min_token_savings=0.30)
        payload = result.to_dict()
        self.assertIn("search_log", payload)
        self.assertTrue(payload["search_log"])
        statuses = {attempt["status"] for attempt in payload["search_log"]}
        self.assertIn("improved", statuses)
        self.assertTrue(any(status in {"flat", "regressed"} for status in statuses))

    def test_lossless_benchmark_respects_requested_tokenizer(self) -> None:
        text = "SEAM preserves exact context while compressing token usage for lossless recovery.\n" * 12
        result = benchmark_text_lossless(text, min_token_savings=0.30, tokenizer="char4_approx")
        self.assertEqual(result.artifact.token_estimator, "char4_approx")

    def test_readable_compression_queries_exact_quote_without_rebuild(self) -> None:
        text = (
            'Project note: "SEAM compression must be directly readable by AI." '
            "The artifact should preserve exact quotes, table cells, numbers, and source spans."
        )
        artifact = compress_text_readable(text, source_ref="unit://readable", tokenizer="char4_approx")
        self.assertTrue(artifact.machine_text.startswith("SEAM-RC/1"))
        self.assertIn("QUOTE|", artifact.machine_text)

        result = query_readable_compressed(artifact.machine_text, '"SEAM compression must be directly readable by AI."')
        self.assertTrue(result.hits)
        self.assertEqual(result.hits[0].record_type, "QUOTE")
        self.assertEqual(result.hits[0].text, '"SEAM compression must be directly readable by AI."')
        self.assertEqual(decompress_text_readable(artifact.machine_text), text)

    def test_cli_readable_compress_and_query_reads_compressed_language(self) -> None:
        source_path = Path(f"readable_source_{uuid4().hex}.txt")
        compressed_path = Path(f"readable_machine_{uuid4().hex}.seamrc")
        try:
            source_text = (
                'Release note: "MIRL is the working compressed document." '
                "SEAM reads the compressed language directly."
            )
            source_path.write_text(source_text, encoding="utf-8")
            with redirect_stdout(StringIO()):
                run_cli(["readable-compress", str(source_path), "--output", str(compressed_path)])
            self.assertTrue(compressed_path.exists())
            self.assertTrue(compressed_path.read_text(encoding="utf-8").startswith("SEAM-RC/1"))

            query_stream = StringIO()
            with redirect_stdout(query_stream):
                run_cli(["readable-query", str(compressed_path), '"MIRL is the working compressed document."'])
            output = query_stream.getvalue()
            self.assertIn("Readable query results", output)
            self.assertIn('"MIRL is the working compressed document."', output)
        finally:
            for path in (source_path, compressed_path):
                if path.exists():
                    path.unlink()

    def test_cli_lossless_compress_and_decompress_roundtrip(self) -> None:
        source_path = Path(f"lossless_source_{uuid4().hex}.txt")
        compressed_path = Path(f"lossless_machine_{uuid4().hex}.seamlx")
        try:
            source_text = ("SEAM preserves exact context while compressing token usage for lossless recovery. " * 16).strip()
            source_path.write_text(source_text, encoding="utf-8")
            compress_stream = StringIO()
            with redirect_stdout(compress_stream):
                run_cli(["lossless-compress", str(source_path), "--output", str(compressed_path), "--format", "json"])
            compressed_payload = compress_stream.getvalue()
            self.assertIn('"machine_text"', compressed_payload)
            self.assertTrue(compressed_path.exists())

            decompress_stream = StringIO()
            with redirect_stdout(decompress_stream):
                run_cli(["lossless-decompress", str(compressed_path)])
            restored = decompress_stream.getvalue().strip()
            self.assertEqual(restored, source_text)
        finally:
            if source_path.exists():
                source_path.unlink()
            if compressed_path.exists():
                compressed_path.unlink()

    def test_cli_lossless_benchmark_json_reports_pass(self) -> None:
        source_path = Path(f"lossless_benchmark_{uuid4().hex}.txt")
        try:
            source_text = "\n".join(["SEAM preserves exact context while compressing token usage for lossless recovery."] * 60)
            source_path.write_text(source_text, encoding="utf-8")
            stream = StringIO()
            with redirect_stdout(stream):
                run_cli(["lossless-benchmark", str(source_path), "--min-savings", "0.75", "--format", "json"])
            payload = stream.getvalue()
            self.assertIn('"passed": true', payload)
            self.assertIn('"roundtrip_match": true', payload)
            self.assertIn('"search_log"', payload)
        finally:
            if source_path.exists():
                source_path.unlink()

    def test_cli_demo_lossless_compress_and_rebuild_roundtrip(self) -> None:
        source_path = Path(f"lossless_demo_source_{uuid4().hex}.txt")
        compressed_path = Path(f"lossless_demo_machine_{uuid4().hex}.seamlx")
        rebuilt_path = Path(f"lossless_demo_rebuilt_{uuid4().hex}.txt")
        log_path = Path(f"lossless_demo_log_{uuid4().hex}.json")
        try:
            source_text = "\n".join(["SEAM preserves exact context while compressing token usage for lossless recovery."] * 60)
            source_path.write_text(source_text, encoding="utf-8")

            compress_stream = StringIO()
            with redirect_stdout(compress_stream):
                run_cli(
                    [
                        "demo",
                        "lossless",
                        str(source_path),
                        str(compressed_path),
                        "--min-savings",
                        "0.75",
                        "--log-output",
                        str(log_path),
                    ]
                )
            self.assertIn("Demo: PASS", compress_stream.getvalue())
            self.assertTrue(compressed_path.exists())
            self.assertTrue(log_path.exists())
            self.assertTrue(compressed_path.read_text(encoding="utf-8").startswith("SEAM-LX/1"))

            rebuild_stream = StringIO()
            with redirect_stdout(rebuild_stream):
                run_cli(["demo", "lossless", str(compressed_path), str(rebuilt_path), "--rebuild"])
            self.assertIn("Demo: REBUILD PASS", rebuild_stream.getvalue())
            self.assertEqual(rebuilt_path.read_text(encoding="utf-8"), source_text)
        finally:
            for path in (source_path, compressed_path, rebuilt_path, log_path):
                if path.exists():
                    path.unlink()

    def test_runtime_benchmark_suite_persists_and_verifies_bundle(self) -> None:
        runtime = SeamRuntime(self.db_path)
        bundle_path = Path(f"benchmark_bundle_{uuid4().hex}.json")
        try:
            report = runtime.run_benchmark_suite(suite="all", persist=True, bundle_path=bundle_path)
            self.assertEqual(report["summary"]["status"], "PASS")
            self.assertEqual(report["summary"]["family_count"], 7)
            self.assertTrue(bundle_path.exists())

            runs = runtime.list_benchmark_runs(limit=1)
            self.assertTrue(runs)
            self.assertEqual(runs[0]["run_id"], report["manifest"]["run_id"])

            loaded = runtime.read_benchmark_run(report["manifest"]["run_id"])
            self.assertEqual(loaded["bundle_hash"], report["bundle_hash"])

            verification = runtime.verify_benchmark_bundle(bundle_path)
            self.assertEqual(verification["status"], "PASS")
            self.assertTrue(verification["bundle_hash_ok"])
        finally:
            if bundle_path.exists():
                bundle_path.unlink()

    def test_runtime_readable_benchmark_compares_rc1_to_source(self) -> None:
        runtime = SeamRuntime(self.db_path)
        report = runtime.run_benchmark_suite(suite="readable", tokenizer="char4_approx")
        self.assertEqual(report["summary"]["status"], "PASS")
        family = report["families"]["readable"]
        self.assertEqual(family["summary"]["direct_text_exact_rate"], 1.0)
        self.assertEqual(family["summary"]["direct_read_equivalence_rate"], 1.0)
        self.assertEqual(family["summary"]["direct_query_exactness_rate"], 1.0)
        self.assertTrue(family["cases"])
        for case in family["cases"]:
            self.assertTrue(case["metrics"]["roundtrip_match"])
            self.assertTrue(case["metrics"]["direct_text_match"])
            self.assertTrue(case["metrics"]["direct_quote_match"])
            self.assertTrue(case["metrics"]["direct_query_exactness"])
            self.assertTrue(case["metrics"]["term_coverage"])
            self.assertTrue(case["metrics"]["info_equivalent"])
        recipe = next(case for case in family["cases"] if case["case_id"] == "rc1_recipe_exact_direct_read")
        self.assertEqual(
            recipe["trace"]["direct_read_text"],
            "\n".join(
                [
                    "Recipe: Lemon Rice",
                    "Yield: 2 servings",
                    "Ingredients:",
                    "- 1 cup cooked rice",
                    "- 1 tablespoon lemon juice",
                    "- 1 teaspoon olive oil",
                    "- 1/4 teaspoon salt",
                    "Steps:",
                    "1. Warm the olive oil in a pan for 30 seconds.",
                    "2. Stir in the cooked rice and salt.",
                    "3. Turn off the heat and fold in the lemon juice.",
                    'Note: "Serve immediately while warm."',
                ]
            ),
        )

    def test_cli_benchmark_readable_json_reports_direct_equivalence(self) -> None:
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["benchmark", "run", "readable", "--tokenizer", "char4_approx", "--format", "json"])
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["summary"]["status"], "PASS")
        self.assertEqual(payload["families"]["readable"]["summary"]["direct_text_exact_rate"], 1.0)
        self.assertEqual(payload["families"]["readable"]["summary"]["direct_read_equivalence_rate"], 1.0)
        self.assertEqual(payload["families"]["readable"]["summary"]["direct_query_exactness_rate"], 1.0)

    def test_benchmark_diff_compares_case_deltas(self) -> None:
        runtime = SeamRuntime(self.db_path)
        before = runtime.run_benchmark_suite(suite="lossless", tokenizer="char4_approx")
        after = json.loads(json.dumps(before))
        case = after["families"]["lossless"]["cases"][0]
        case["metrics"]["token_savings_ratio"] = round(case["metrics"]["token_savings_ratio"] + 0.05, 6)
        after["families"]["lossless"]["cases"][0] = benchmark_module._stamp_case_hash(case)
        after["summary"] = benchmark_module._build_suite_summary(after["families"])
        after["bundle_hash"] = benchmark_module._hash_payload(after, "bundle_hash")

        diff = runtime.diff_benchmark_runs(before, after)
        self.assertEqual(diff["summary"]["cases_compared"], before["summary"]["case_count"])
        self.assertEqual(diff["summary"]["changed_case_matches"], 1)
        changed = [item for item in diff["cases"] if item["case_hash_changed"]]
        self.assertEqual(len(changed), 1)
        savings_delta = [item for item in changed[0]["metric_deltas"] if item["metric"] == "token_savings_ratio"][0]
        self.assertEqual(savings_delta["indicator"], "green")

    def test_benchmark_gate_passes_custom_lossless_policy(self) -> None:
        runtime = SeamRuntime(self.db_path)
        report = runtime.run_benchmark_suite(suite="lossless", tokenizer="char4_approx")
        policy = {
            "version": benchmark_module.BENCHMARK_GATE_VERSION,
            "required_families": ["lossless"],
            "summary": {
                "status": {"equals": "PASS"},
                "family_count": {"minimum": 1},
                "case_count": {"minimum": 2},
            },
            "families": {
                "lossless": {
                    "pass_rate": {"minimum": 1.0},
                    "exactness_rate": {"minimum": 1.0},
                }
            },
            "baseline": {
                "status_regressions": {"maximum": 0},
                "metric_regressions": {"maximum": 0},
                "removed_cases": {"maximum": 0},
            },
        }

        gate = runtime.evaluate_benchmark_gate(report, policy=policy)
        self.assertEqual(gate["status"], "PASS")
        self.assertEqual(gate["summary"]["failed"], 0)
        self.assertTrue(all(check["status"] == "PASS" for check in gate["checks"]))

    def test_benchmark_gate_flags_threshold_failure(self) -> None:
        runtime = SeamRuntime(self.db_path)
        report = runtime.run_benchmark_suite(suite="lossless", tokenizer="char4_approx")
        policy = {
            "version": benchmark_module.BENCHMARK_GATE_VERSION,
            "required_families": ["lossless"],
            "summary": {"status": {"equals": "PASS"}},
            "families": {"lossless": {"worst_case_savings": {"minimum": 1.0}}},
            "baseline": {},
        }

        gate = runtime.evaluate_benchmark_gate(report, policy=policy)
        self.assertEqual(gate["status"], "FAIL")
        failed = [check for check in gate["checks"] if check["status"] == "FAIL"]
        self.assertTrue(any(check["metric"] == "worst_case_savings" for check in failed))

    def test_cli_benchmark_diff_json_accepts_bundle_paths(self) -> None:
        runtime = SeamRuntime(self.db_path)
        first_path = Path(f"benchmark_diff_a_{uuid4().hex}.json")
        second_path = Path(f"benchmark_diff_b_{uuid4().hex}.json")
        try:
            first = runtime.run_benchmark_suite(suite="lossless", tokenizer="char4_approx", bundle_path=first_path)
            second = json.loads(json.dumps(first))
            second["families"]["lossless"]["cases"][0]["status"] = "FAIL"
            second["families"]["lossless"]["cases"][0] = benchmark_module._stamp_case_hash(second["families"]["lossless"]["cases"][0])
            second["summary"] = benchmark_module._build_suite_summary(second["families"])
            second["bundle_hash"] = benchmark_module._hash_payload(second, "bundle_hash")
            second_path.write_text(json.dumps(second, indent=2), encoding="utf-8")

            stream = StringIO()
            with redirect_stdout(stream):
                run_cli(["--db", str(self.db_path), "benchmark", "diff", str(first_path), str(second_path), "--format", "json"])
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["summary"]["status_regressions"], 1)
            self.assertEqual(payload["summary"]["status"], "REGRESSED")
        finally:
            for path in (first_path, second_path):
                if path.exists():
                    path.unlink()

    def test_cli_benchmark_gate_exits_nonzero_on_baseline_regression(self) -> None:
        runtime = SeamRuntime(self.db_path)
        baseline_path = Path(f"benchmark_gate_a_{uuid4().hex}.json")
        candidate_path = Path(f"benchmark_gate_b_{uuid4().hex}.json")
        policy_path = Path(f"benchmark_gate_policy_{uuid4().hex}.json")
        try:
            baseline = runtime.run_benchmark_suite(suite="lossless", tokenizer="char4_approx", bundle_path=baseline_path)
            candidate = json.loads(json.dumps(baseline))
            candidate["families"]["lossless"]["cases"][0]["status"] = "FAIL"
            candidate["families"]["lossless"]["cases"][0] = benchmark_module._stamp_case_hash(candidate["families"]["lossless"]["cases"][0])
            candidate["summary"] = benchmark_module._build_suite_summary(candidate["families"])
            candidate["bundle_hash"] = benchmark_module._hash_payload(candidate, "bundle_hash")
            candidate_path.write_text(json.dumps(candidate, indent=2), encoding="utf-8")
            policy_path.write_text(
                json.dumps(
                    {
                        "version": benchmark_module.BENCHMARK_GATE_VERSION,
                        "required_families": ["lossless"],
                        "summary": {},
                        "families": {},
                        "baseline": {"status_regressions": {"maximum": 0}},
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            stream = StringIO()
            with redirect_stdout(stream), self.assertRaises(SystemExit) as raised:
                run_cli(
                    [
                        "--db",
                        str(self.db_path),
                        "benchmark",
                        "gate",
                        str(candidate_path),
                        "--baseline",
                        str(baseline_path),
                        "--policy",
                        str(policy_path),
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(raised.exception.code, 1)
            payload = json.loads(stream.getvalue())
            self.assertEqual(payload["status"], "FAIL")
            self.assertEqual(payload["baseline_diff"]["summary"]["status_regressions"], 1)
        finally:
            for path in (baseline_path, candidate_path, policy_path):
                if path.exists():
                    path.unlink()

    def test_cli_benchmark_holdout_requires_confirmation(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            run_cli(["benchmark", "run", "lossless", "--holdout", "--format", "json"])
        self.assertIn("--confirm-holdout", str(raised.exception))

    def test_cli_benchmark_holdout_uses_private_fixture_and_separate_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="seam-holdout-fixtures-") as fixture_dir, tempfile.TemporaryDirectory(
            prefix="seam-holdout-runs-"
        ) as run_dir:
            fixture_root = Path(fixture_dir)
            run_root = Path(run_dir)
            (fixture_root / "lossless_cases.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "private_lossless_repeat",
                            "text": "Holdout compression phrase stays hidden during tuning.\n" * 24,
                            "min_token_savings": 0.30,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with patch.object(benchmark_module, "HOLDOUT_FIXTURE_ROOT", fixture_root), patch.object(
                benchmark_module, "HOLDOUT_RUN_ROOT", run_root
            ):
                stream = StringIO()
                with redirect_stdout(stream):
                    run_cli(["benchmark", "run", "lossless", "--holdout", "--confirm-holdout", "--tokenizer", "char4_approx", "--format", "json"])
                payload = json.loads(stream.getvalue())
                self.assertEqual(payload["manifest"]["fixture_scope"], "holdout")
                self.assertTrue(payload["manifest"]["publish_only"])
                self.assertEqual(payload["manifest"]["executed_suites"], ["lossless"])
                self.assertEqual(payload["families"]["lossless"]["cases"][0]["case_id"], "private_lossless_repeat")
                self.assertTrue(list(run_root.glob("*.json")))

    def test_runtime_benchmark_verifier_flags_tampered_bundle(self) -> None:
        runtime = SeamRuntime(self.db_path)
        bundle_path = Path(f"benchmark_bundle_{uuid4().hex}.json")
        tampered_path = Path(f"benchmark_bundle_tampered_{uuid4().hex}.json")
        try:
            runtime.run_benchmark_suite(suite="lossless", bundle_path=bundle_path)
            payload = json.loads(bundle_path.read_text(encoding="utf-8"))
            payload["families"]["lossless"]["cases"][0]["metrics"]["roundtrip_match"] = False
            tampered_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            verification = runtime.verify_benchmark_bundle(tampered_path)
            self.assertEqual(verification["status"], "FAIL")
            self.assertFalse(verification["bundle_hash_ok"])
            self.assertTrue(any(not item["ok"] for item in verification["case_checks"]))
        finally:
            for target in (bundle_path, tampered_path):
                if target.exists():
                    target.unlink()

    def test_storage_machine_artifact_and_projection_roundtrip(self) -> None:
        runtime = SeamRuntime(self.db_path)
        artifact = compress_text_lossless("SEAM preserves exact context while compressing token usage for lossless recovery.\n" * 10)
        artifact_id = runtime.store.write_machine_artifact(
            source_type="test.machine",
            source_id="machine-roundtrip",
            artifact=artifact.to_dict(include_machine_text=True),
            roundtrip_ok=True,
            metadata={"suite": "unit"},
        )
        loaded_artifact = runtime.store.read_machine_artifact(artifact_id)
        self.assertTrue(loaded_artifact["roundtrip_ok"])
        self.assertEqual(loaded_artifact["metadata"], {"suite": "unit"})
        self.assertTrue(str(loaded_artifact["machine_text"]).startswith("SEAM-LX/1"))

        projection_id = runtime.store.write_projection(
            record_id="clm:test",
            projection_kind="prompt",
            projection_text="SEAM retrieved context\n[1] clm:test [CLM] translator_for natural_language",
            tokenizer="char4_approx",
            token_count=17,
            metadata={"suite": "unit"},
        )
        projections = runtime.store.read_projections(record_id="clm:test", projection_kind="prompt")
        self.assertEqual(len(projections), 1)
        self.assertEqual(projections[0]["projection_id"], projection_id)
        self.assertEqual(projections[0]["metadata"], {"suite": "unit"})

    def test_cli_benchmark_show_latest_reads_persisted_run(self) -> None:
        bundle_path = Path(f"benchmark_cli_bundle_{uuid4().hex}.json")
        try:
            run_stream = StringIO()
            with redirect_stdout(run_stream):
                run_cli([
                    "--db",
                    str(self.db_path),
                    "benchmark",
                    "run",
                    "lossless",
                    "--persist",
                    "--output",
                    str(bundle_path),
                    "--format",
                    "json",
                ])
            payload = run_stream.getvalue()
            self.assertIn('"requested_suite": "lossless"', payload)

            show_stream = StringIO()
            with redirect_stdout(show_stream):
                run_cli(["--db", str(self.db_path), "benchmark", "show", "latest", "--format", "json"])
            show_payload = show_stream.getvalue()
            self.assertIn('"requested_suite": "lossless"', show_payload)
            self.assertIn('"bundle_hash"', show_payload)
        finally:
            if bundle_path.exists():
                bundle_path.unlink()

    def test_cli_compile_nl_rag_sync_persists_and_syncs(self) -> None:
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(
                [
                    "--db",
                    str(self.db_path),
                    "compile-nl",
                    "We need a translator back into natural language for memory workflows.",
                    "--index",
                ]
            )
        runtime = SeamRuntime(self.db_path)
        records = runtime.store.load_ir().records
        self.assertTrue(records)

    def test_cli_doctor_reports_pass(self) -> None:
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["doctor"])
        payload = stream.getvalue()
        required = ["rich", "chromadb", "tiktoken"]
        missing = [name for name in required if find_spec(name) is None]
        expected = "PASS" if not missing else "FAIL"
        self.assertIn(f"SEAM doctor: {expected}", payload)
        self.assertIn("Compile smoke: PASS", payload)
        self.assertIn("PgVector:", payload)
        self.assertIn("Required deps:", payload)

    def test_cli_doctor_reports_pgvector_not_configured_when_dsn_absent(self) -> None:
        old = os.environ.pop("SEAM_PGVECTOR_DSN", None)
        try:
            stream = StringIO()
            with redirect_stdout(stream):
                run_cli(["doctor"])
            self.assertIn("PgVector: not configured", stream.getvalue())
        finally:
            if old is not None:
                os.environ["SEAM_PGVECTOR_DSN"] = old

    def test_cli_doctor_json_reports_dependency_status(self) -> None:
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["doctor", "--format", "json"])
        payload = json.loads(stream.getvalue())
        required = ["rich", "chromadb", "tiktoken"]
        missing = [name for name in required if find_spec(name) is None]
        expected = "PASS" if not missing else "FAIL"
        self.assertEqual(payload["status"], expected)
        self.assertIn("dependencies", payload)
        self.assertIn("required_dependencies", payload)
        self.assertIn("missing_required_dependencies", payload)
        self.assertEqual(sorted(payload["required_dependencies"]), sorted(required))
        self.assertEqual(sorted(payload["missing_required_dependencies"]), sorted(missing))
        self.assertIn("psycopg", payload["dependencies"])
        self.assertIn("sentence_transformers", payload["dependencies"])
        self.assertIn("pgvector", payload)
        self.assertIn("configured", payload["pgvector"])

    def test_installer_windows_shim_sets_persistent_db(self) -> None:
        shim = render_windows_cmd_shim(
            Path(r"C:\SEAM\runtime\Scripts\seam.exe"),
            Path(r"C:\Repos\Seam"),
            r'powershell -ExecutionPolicy Bypass -File "C:\Repos\Seam\installers\install_seam_windows.ps1"',
            Path(r"C:\Users\iwana\AppData\Local\SEAM\state\seam.db"),
        )
        self.assertIn("SEAM_DB_PATH", shim)
        self.assertIn(r"C:\Users\iwana\AppData\Local\SEAM\state\seam.db", shim)

    def test_installer_posix_shim_sets_persistent_db(self) -> None:
        shim = render_posix_shim(
            Path("/home/iwana/.local/share/seam/runtime/bin/seam"),
            Path("/repos/seam"),
            '"/repos/seam/installers/install_seam_linux.sh"',
            Path("/home/iwana/.local/share/seam/state/seam.db"),
        )
        self.assertIn('export SEAM_DB_PATH="/home/iwana/.local/share/seam/state/seam.db"', shim)

    def test_default_runtime_db_path_prefers_env(self) -> None:
        original = os.environ.get("SEAM_DB_PATH")
        try:
            os.environ["SEAM_DB_PATH"] = "custom-seam.db"
            self.assertEqual(default_runtime_db_path(), "custom-seam.db")
        finally:
            if original is None:
                os.environ.pop("SEAM_DB_PATH", None)
            else:
                os.environ["SEAM_DB_PATH"] = original

    def test_dashboard_snapshot_renders_runtime_metrics(self) -> None:
        if Console is None:
            self.skipTest("rich is not installed")
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        stream = StringIO()
        console = Console(file=stream, force_terminal=False, color_system=None, width=140)
        run_dashboard(runtime, snapshot=True, no_clear=True, console=console)
        output = stream.getvalue()
        self.assertIn("SEAM Console", output)
        self.assertIn("Storage", output)
        self.assertIn("Records", output)

    def test_dashboard_script_handles_success_and_error(self) -> None:
        if Console is None:
            self.skipTest("rich is not installed")
        runtime = SeamRuntime(self.db_path)
        stream = StringIO()
        console = Console(file=stream, force_terminal=False, color_system=None, width=140)
        run_dashboard(
            runtime,
            no_clear=True,
            console=console,
            commands=[
                "compile We need a translator back into natural language for memory workflows.",
                "retrieve translator natural language --budget 3",
                "trace missing:id",
            ],
        )
        output = stream.getvalue()
        self.assertIn("SEAM Console", output)
        self.assertIn("missing:id", output)
        self.assertIn("Runtime Log", output)

    def test_mirl_animation_settles_on_completed_frame(self) -> None:
        engine = AnimationEngine(height=4)
        self.assertFalse(engine.active)
        self.assertIn("Idle", "\n".join(engine.tick_and_render(now=0.0)))

        engine.trigger_compress("compile", source_tokens=90, machine_tokens=30, kind="compile")
        rows: list[str] = []
        for tick in range(40):
            rows = engine.tick_and_render(now=tick * 0.25)

        self.assertFalse(engine.active)
        self.assertTrue(engine.has_completed_frame)
        self.assertIn("complete", "\n".join(rows))
        self.assertEqual(rows, engine.tick_and_render(now=30.0))

    def test_dashboard_benchmark_tab_renders_benchmark_surface(self) -> None:
        if Console is None:
            self.skipTest("rich is not installed")
        runtime = SeamRuntime(self.db_path)
        source_path = Path(f"lossless_dashboard_{uuid4().hex}.txt")
        try:
            source_path.write_text(
                ("SEAM preserves exact context while compressing token usage for lossless recovery. " * 20).strip(),
                encoding="utf-8",
            )
            stream = StringIO()
            console = Console(file=stream, force_terminal=False, color_system=None, width=160)
            run_dashboard(
                runtime,
                no_clear=True,
                console=console,
                commands=[
                    "tab benchmark",
                    f"benchmark {source_path} --min-savings 0.75",
                ],
            )
            output = stream.getvalue()
            self.assertIn("Benchmark", output)
            self.assertIn("Search log", output)
        finally:
            if source_path.exists():
                source_path.unlink()

    def test_dashboard_reload_refreshes_scripted_runtime_view(self) -> None:
        if Console is None:
            self.skipTest("rich is not installed")
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("SEAM reload should refresh dashboard runtime charts."))
        stream = StringIO()
        console = Console(file=stream, force_terminal=False, color_system=None, width=160)
        run_dashboard(runtime, no_clear=True, console=console, commands=["reload"])
        output = stream.getvalue()
        self.assertIn("Reload", output)
        self.assertIn("reloaded", output)
        self.assertIn("Records", output)

    def test_textual_dashboard_mounts_core_panels(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                # IDE layout: panels exist in DOM regardless of which tab is active
                self.assertIsNotNone(app.query_one("#memory-panel"))
                self.assertIsNotNone(app.query_one("#retrieval-panel"))
                self.assertIsNotNone(app.query_one("#benchmark-panel"))
                self.assertIsNotNone(app.query_one("#overview-panel"))
                self.assertIsNotNone(app.query_one("#mirl-panel"))
                self.assertIsNotNone(app.query_one("#prov-panel"))
                self.assertIsNotNone(app.query_one("#explorer-panel"))
                self.assertIsNotNone(app.query_one("#ide-layout"))
                self.assertIsNotNone(app.query_one("#right-col"))
                self.assertIsNotNone(app.query_one("#chat-panel"))
                self.assertIsNotNone(app.query_one("#result-panel"))
                self.assertIsNotNone(app.query_one("#command-palette"))
                self.assertIsNotNone(app.query_one("#command-input"))

        asyncio.run(_check())

    def test_textual_dashboard_settings_apply_api_updates_env(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        from textual.widgets import TabbedContent

        saved = {
            "SEAM_CHAT_API_KEY": os.environ.get("SEAM_CHAT_API_KEY"),
            "SEAM_CHAT_BASE_URL": os.environ.get("SEAM_CHAT_BASE_URL"),
            "SEAM_CHAT_MODEL": os.environ.get("SEAM_CHAT_MODEL"),
        }
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test(size=(160, 60)) as pilot:
                await pilot.pause()
                app.query_one("#main-tabs", TabbedContent).active = "tab-settings"
                await pilot.pause()
                app.query_one("#cfg-api-key").value = "test-settings-key"
                app.query_one("#cfg-base-url").value = "https://example.invalid/v1"
                app.query_one("#cfg-model").value = "test-model"
                await pilot.click("#btn-apply-api")
                await pilot.pause()
                self.assertEqual(os.environ.get("SEAM_CHAT_API_KEY"), "test-settings-key")
                self.assertEqual(os.environ.get("SEAM_CHAT_BASE_URL"), "https://example.invalid/v1")
                self.assertEqual(os.environ.get("SEAM_CHAT_MODEL"), "test-model")
                self.assertTrue(any("Applied: SEAM_CHAT_API_KEY" in line for line in app.result_lines))

        try:
            asyncio.run(_check())
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_textual_dashboard_command_palette_filters_prefix_menus(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app._update_command_palette("/retr")
                await pilot.pause()
                self.assertTrue(app._palette_matches)
                self.assertEqual(app._palette_matches[0].trigger, "/")
                self.assertEqual(app._palette_matches[0].command, "retrieve")

                app._update_command_palette("/")
                await pilot.pause()
                slash_commands = {item.command for item in app._palette_matches}
                self.assertIn("compile", slash_commands)
                self.assertIn("retrieve", slash_commands)
                self.assertIn("reload", slash_commands)
                self.assertIn("agent", slash_commands)
                self.assertIn("shell", slash_commands)
                self.assertIn("model", slash_commands)

                app._update_command_palette("!git")
                await pilot.pause()
                self.assertTrue(app._palette_matches)
                self.assertEqual(app._palette_matches[0].trigger, "!")
                self.assertIn("git", app._palette_matches[0].command)

                app._update_command_palette("?mod")
                await pilot.pause()
                self.assertTrue(app._palette_matches)
                self.assertEqual(app._palette_matches[0].trigger, "?")
                self.assertEqual(app._palette_matches[0].command, "model")

        asyncio.run(_check())

    def test_textual_dashboard_command_palette_accepts_selection(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                input_widget = app.query_one("#command-input")
                app._update_command_palette("/stats")
                await pilot.pause()
                app._accept_palette_selection(input_widget, submit=True)
                await pilot.pause()
                self.assertEqual(app.controller.result_title, "Stats")
                self.assertEqual(input_widget.value, "")

                app.process_command("/stats")
                await pilot.pause()
                self.assertEqual(app.controller.result_title, "Stats")

                app.process_command("/reload")
                await pilot.pause()
                self.assertEqual(app.controller.result_title, "Reload")

                app._update_command_palette("/compile")
                await pilot.pause()
                app._accept_palette_selection(input_widget, submit=True)
                await pilot.pause()
                self.assertEqual(input_widget.value, "/compile ")

        asyncio.run(_check())

    def test_textual_dashboard_reload_refreshes_panels_after_runtime_change(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                runtime.persist_ir(runtime.compile_nl("Reload refreshes dashboard metrics after external writes."))
                app.process_command("!reload")
                await pilot.pause()
                self.assertEqual(app.controller.result_title, "Reload")
                self.assertIn('"status": "reloaded"', "\n".join(app.result_lines))
                explorer = app.query_one("#explorer-panel")
                overview = app.query_one("#overview-panel")
                self.assertIn("memory", "\n".join(explorer._panel_lines))
                self.assertIn("Total", "\n".join(overview._panel_lines))
                self.assertTrue(any("Reload" in line for line in app.memory_lines))

        asyncio.run(_check())

    def test_textual_dashboard_explorer_lazy_loads_namespaces(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(
            runtime.compile_nl(
                "Explorer namespace lazy loading should reveal persisted memory records.",
                ns="local.default",
                scope="thread",
            )
        )
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                explorer = app.query_one("#explorer-panel")
                explorer.populate_db(app.controller._collect_metrics())
                ns_root = next(
                    child
                    for child in explorer._db_root.children
                    if (child.data or {}).get("type") == "ns_root"
                )
                explorer._lazy_expand_namespaces(ns_root)
                namespace_labels = [str(child.label) for child in ns_root.children]
                self.assertTrue(any("local.default" in label for label in namespace_labels))
                ns_node = next(
                    child
                    for child in ns_root.children
                    if (child.data or {}).get("ns") == "local.default"
                )
                explorer._lazy_expand_namespace(ns_node, "local.default")
                scope_labels = [str(child.label) for child in ns_node.children]
                self.assertTrue(any("thread" in label for label in scope_labels))

        asyncio.run(_check())

    def test_textual_dashboard_routes_retrieval_output(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        runtime.persist_ir(runtime.compile_nl("We need a translator back into natural language for memory workflows."))
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.process_command("!retrieve translator natural language --budget 3")
                await pilot.pause()
                joined = "\n".join(app.retrieval_lines)
                self.assertIn("retrieve translator natural language", joined)
                self.assertIn("clm:2", joined)

        asyncio.run(_check())

    def test_textual_dashboard_chat_panel_sits_above_input(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                # In the IDE layout the right column (#right-col) holds chat
                # and result panels; it must sit above the docked command input.
                right_col = app.query_one("#right-col")
                command_input = app.query_one("#command-input")
                self.assertLess(right_col.region.y, command_input.region.y)

        asyncio.run(_check())

    def test_textual_dashboard_panels_autofollow_latest_output(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                for idx in range(320):
                    app._record_command("run", f"command-{idx}")
                await pilot.pause()
                panel = app.query_one("#command-history-panel")
                self.assertTrue(panel.can_focus)
                self.assertGreater(panel.max_scroll_y, 0)
                self.assertGreaterEqual(panel.scroll_y, panel.max_scroll_y - 1.0)

        asyncio.run(_check())

    def test_textual_dashboard_focused_panel_supports_keyboard_scrolling(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause()
                for idx in range(500):
                    app._record_command("run", f"command-{idx}")
                # Switch to the Live tab where #command-history-panel lives
                from textual.widgets import TabbedContent
                app.query_one("#main-tabs", TabbedContent).active = "tab-live"
                await pilot.pause()
                panel = app.query_one("#command-history-panel")
                await pilot.click("#command-history-panel")
                await pilot.pause()
                self.assertIs(app.focused, panel)
                before = panel.scroll_y
                await pilot.press("pageup")
                await pilot.pause()
                after_pageup = panel.scroll_y
                await pilot.press("pagedown")
                await pilot.pause()
                after_pagedown = panel.scroll_y
                self.assertLess(after_pageup, before)
                self.assertGreater(after_pagedown, after_pageup)

        asyncio.run(_check())

    def test_textual_dashboard_routes_compile_output(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.process_command("!compile We need durable memory for AI systems")
                await pilot.pause()
                joined = "\n".join(app.memory_lines)
                self.assertIn("Compile", joined)
                self.assertIn("\"persist\"", joined)

        asyncio.run(_check())

    def test_textual_dashboard_hybrid_mode_routes_bare_commands(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.process_command("help")
                await pilot.pause()
                self.assertEqual(app.controller.result_title, "Dashboard Help")

        asyncio.run(_check())

    def test_textual_dashboard_tab_switch_updates_side_panel_mode(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        from textual.widgets import TabbedContent
        runtime = SeamRuntime(self.db_path)
        source_path = Path(f"lossless_textual_{uuid4().hex}.txt")
        source_path.write_text(("SEAM preserves exact context while compressing token usage. " * 10).strip(), encoding="utf-8")
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                # Switching to benchmark via the tab command should activate that tab
                app.process_command("!tab benchmark")
                await pilot.pause()
                tabs = app.query_one("#main-tabs", TabbedContent)
                self.assertEqual(tabs.active, "tab-benchmarks")

                # Running a benchmark populates benchmark_lines and switches the tab
                app.process_command(f"!benchmark {source_path} --min-savings 0.75")
                await pilot.pause()
                self.assertTrue(any("Benchmark" in line for line in app.benchmark_lines))

                # Switching back to runtime shows overview tab
                app.process_command("!tab runtime")
                await pilot.pause()
                self.assertNotEqual(tabs.active, "tab-benchmarks")

        try:
            asyncio.run(_check())
        finally:
            if source_path.exists():
                source_path.unlink()

    def test_textual_dashboard_shortcuts_switch_modes(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.process_command("?shell")
                await pilot.pause()
                self.assertEqual(app.input_mode, "shell")
                app.process_command("?seam")
                await pilot.pause()
                self.assertEqual(app.input_mode, "seam")
                app.process_command("?agent")
                await pilot.pause()
                self.assertEqual(app.input_mode, "agent")
                app.process_command("?hybrid")
                await pilot.pause()
                self.assertEqual(app.input_mode, "hybrid")

        asyncio.run(_check())

    def test_textual_dashboard_shortcuts_switch_chat_model(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.process_command("?model gpt-4.1-mini")
                await pilot.pause()
                self.assertEqual(app.chat_client.model, "gpt-4.1-mini")
                self.assertIn("Switched chat model to gpt-4.1-mini", "\n".join(app.result_lines))

        asyncio.run(_check())

    def test_dashboard_default_chat_models_include_openrouter_agent_models(self) -> None:
        expected = {
            "openrouter/pareto-code",
            "qwen/qwen3-coder",
            "qwen/qwen3-coder-next",
            "qwen/qwen3-coder-plus",
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-v4-flash",
            "xiaomi/mimo-v2.5-pro",
            "xiaomi/mimo-v2.5",
            "moonshotai/kimi-k2.6",
            "z-ai/glm-5.1",
            "x-ai/grok-4.20",
            "x-ai/grok-4.20-multi-agent",
            "x-ai/grok-4.1-fast",
            "x-ai/grok-code-fast-1",
            "google/gemma-4-31b-it",
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it",
            "google/gemma-4-26b-a4b-it:free",
        }
        self.assertTrue(expected.issubset(set(DEFAULT_CHAT_MODELS)))
        with patch.dict(os.environ, {"SEAM_CHAT_MODEL": "gpt-4o-mini"}, clear=True):
            self.assertTrue(expected.issubset(set(SeamChatClient().available_models)))

    def test_textual_dashboard_bang_runs_shell_commands(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.process_command("!pwd")
                await pilot.pause()
                self.assertIn("Shell", "\n".join(app.result_lines))
                self.assertIn(str(app.shell_cwd), "\n".join(app.result_lines))
                history = "\n".join(app.command_history_lines)
                self.assertIn("[SHELL] pwd", history)

        asyncio.run(_check())

    def test_textual_dashboard_double_question_forces_chat_outside_agent_mode(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.process_command("?shell")
                await pilot.pause()
                app.process_command("??What mode am I in?")
                await pilot.pause()
                self.assertGreaterEqual(len(app.chat_history), 2)
                self.assertEqual(app.chat_history[0]["role"], "user")
                self.assertEqual(app.chat_history[0]["content"], "What mode am I in?")

        asyncio.run(_check())

    def test_textual_dashboard_shortcuts_export_chat_transcript(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)
        export_path = Path(f"chat_export_{uuid4().hex}.jsonl")

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.process_command("What is the active mode?")
                await pilot.pause()
                app.process_command(f"?savechat {export_path}")
                await pilot.pause()
                self.assertTrue(export_path.exists())
                rows = [line.strip() for line in export_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertGreaterEqual(len(rows), 2)
                self.assertTrue(any('"role": "user"' in line for line in rows))
                self.assertTrue(any('"role": "assistant"' in line for line in rows))

        try:
            asyncio.run(_check())
        finally:
            if export_path.exists():
                export_path.unlink()

    def test_textual_dashboard_command_history_includes_status_badges_and_timing(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        runtime = SeamRuntime(self.db_path)
        app = TextualDashboardApp(runtime)

        async def _check() -> None:
            async with app.run_test() as pilot:
                await pilot.pause()
                app.process_command("!help")
                await pilot.pause()
                app.process_command("!trace missing:id")
                await pilot.pause()
                history = "\n".join(app.command_history_lines)
                self.assertIn("[RUN] help", history)
                self.assertIn("[OK] help -> Dashboard Help", history)
                self.assertIn("[ERR] trace missing:id -> KeyError", history)
                self.assertRegex(history, r"\(\d+ms\)|\(\d+\.\d+s\)")

        asyncio.run(_check())

    def test_textual_dashboard_routes_readable_rc1_commands(self) -> None:
        if find_spec("textual") is None:
            self.skipTest("textual is not installed")
        source_path = Path(f"dashboard_readable_{uuid4().hex}.txt")
        rc_path = Path(f"dashboard_readable_{uuid4().hex}.seamrc")
        try:
            source_path.write_text(
                'Recipe: Lemon Rice\nYield: 2 bowls\nNote: "Toast the rice before adding broth."\n',
                encoding="utf-8",
            )
            runtime = SeamRuntime(self.db_path)
            app = TextualDashboardApp(runtime)

            async def _check() -> None:
                async with app.run_test() as pilot:
                    await pilot.pause()
                    app.process_command(f"!readable-compress {source_path.resolve()} --granularity line")
                    await pilot.pause()
                    self.assertEqual(app.controller.result_title, "Readable Compress")
                    rc_path.write_text(str(app.controller.last_machine_text), encoding="utf-8")

                    app.process_command(f"!readable-query {rc_path.resolve()} Toast rice --limit 3")
                    await pilot.pause()
                    self.assertEqual(app.controller.result_title, "Readable Query")
                    self.assertIn("Toast the rice", "\n".join(app.benchmark_lines))

                    app.process_command(f"!readable-rebuild {rc_path.resolve()}")
                    await pilot.pause()
                    self.assertEqual(app.controller.result_title, "Readable Rebuild")
                    self.assertIn("Recipe: Lemon Rice", "\n".join(app.benchmark_lines))

            asyncio.run(_check())
        finally:
            if source_path.exists():
                source_path.unlink()
            if rc_path.exists():
                rc_path.unlink()

class InstallerLinuxTests(unittest.TestCase):
    def test_posix_shim_has_valid_sh_structure(self) -> None:
        shim = render_posix_shim(
            Path("/home/user/.local/share/seam/runtime/bin/seam"),
            Path("/home/user/seam"),
            '"/home/user/seam/installers/install_seam_linux.sh"',
            Path("/home/user/.local/share/seam/state/seam.db"),
        )
        self.assertTrue(shim.startswith("#!/usr/bin/env sh\n"))
        self.assertIn('SEAM_EXE="/home/user/.local/share/seam/runtime/bin/seam"', shim)
        self.assertIn('export SEAM_DB_PATH="/home/user/.local/share/seam/state/seam.db"', shim)
        self.assertIn('if [ ! -x "$SEAM_EXE" ]', shim)
        self.assertIn('exec "$SEAM_EXE" "$@"', shim)

    def test_path_in_environment_finds_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "bin"
            target.mkdir()
            path_string = os.pathsep.join(["/usr/bin", str(target), "/usr/local/bin"])
            self.assertTrue(path_in_environment(target, path_string))

    def test_path_in_environment_returns_false_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "bin"
            path_string = os.pathsep.join(["/usr/bin", "/usr/local/bin"])
            self.assertFalse(path_in_environment(target, path_string))

    def test_posix_profile_injection_adds_path_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            target = home / "bin"
            original_path = os.environ.get("PATH", "")
            try:
                with patch("pathlib.Path.home", return_value=home):
                    updated = _ensure_posix_shell_profiles(target)
                bashrc = home / ".bashrc"
                self.assertTrue(bashrc.exists())
                content = bashrc.read_text()
                self.assertIn(PATH_MARKER_BEGIN, content)
                self.assertIn(str(target), content)
                self.assertGreater(len(updated), 0)
            finally:
                os.environ["PATH"] = original_path

    def test_posix_profile_skips_injection_if_marker_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            target = home / "bin"
            marker_block = f"{PATH_MARKER_BEGIN}\nexport PATH=\"{target}:$PATH\"\n# <<< SEAM installer <<<\n"
            for name in (".profile", ".bashrc", ".zprofile"):
                (home / name).write_text(marker_block, encoding="utf-8")
            original_path = os.environ.get("PATH", "")
            try:
                with patch("pathlib.Path.home", return_value=home):
                    updated = _ensure_posix_shell_profiles(target)
                self.assertEqual(updated, [])
            finally:
                os.environ["PATH"] = original_path

    def test_linux_installer_sh_delegates_to_python(self) -> None:
        sh_path = Path(__file__).resolve().parent / "installers" / "install_seam_linux.sh"
        content = sh_path.read_text()
        self.assertTrue(content.startswith("#!/usr/bin/env sh"))
        self.assertIn("python3", content)
        self.assertIn("install_seam.py", content)
        self.assertIn("set -eu", content)

    def test_detect_layout_includes_dashboard_entry(self) -> None:
        layout = detect_layout()
        self.assertIn("seam-dash", layout.dashboard_entry.name)
        if layout.is_windows:
            self.assertEqual(layout.dashboard_entry.name, "seam-dash.exe")
            self.assertEqual(layout.dashboard_entry.parent, layout.venv_dir / "Scripts")
        else:
            self.assertEqual(layout.dashboard_entry.name, "seam-dash")
            self.assertEqual(layout.dashboard_entry.parent, layout.venv_dir / "bin")

    def test_write_shims_returns_three_paths_posix_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            install_root = root / "install"
            venv_dir = install_root / "runtime"
            bin_dir = install_root / "bin"
            layout = InstallLayout(
                repo_root=repo_root,
                install_root=install_root,
                venv_dir=venv_dir,
                bin_dir=bin_dir,
                seam_entry=venv_dir / "bin" / "seam",
                benchmark_entry=venv_dir / "bin" / "seam-benchmark",
                dashboard_entry=venv_dir / "bin" / "seam-dash",
                persistent_db_path=install_root / "state" / "seam.db",
                is_windows=False,
            )
            seam_shim, benchmark_shim, dashboard_shim = write_shims(layout)
            self.assertEqual(seam_shim, bin_dir / "seam")
            self.assertEqual(benchmark_shim, bin_dir / "seam-benchmark")
            self.assertEqual(dashboard_shim, bin_dir / "seam-dash")
            self.assertTrue(dashboard_shim.exists())
            content = dashboard_shim.read_text(encoding="utf-8")
            self.assertIn("seam-dash", content)
            self.assertIn('export SEAM_DB_PATH=', content)

    def test_write_shims_returns_three_paths_windows_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            install_root = root / "install"
            venv_dir = install_root / "runtime"
            bin_dir = install_root / "bin"
            layout = InstallLayout(
                repo_root=repo_root,
                install_root=install_root,
                venv_dir=venv_dir,
                bin_dir=bin_dir,
                seam_entry=venv_dir / "Scripts" / "seam.exe",
                benchmark_entry=venv_dir / "Scripts" / "seam-benchmark.exe",
                dashboard_entry=venv_dir / "Scripts" / "seam-dash.exe",
                persistent_db_path=install_root / "state" / "seam.db",
                is_windows=True,
            )
            seam_shim, benchmark_shim, dashboard_shim = write_shims(layout)
            self.assertEqual(seam_shim, bin_dir / "seam.cmd")
            self.assertEqual(benchmark_shim, bin_dir / "seam-benchmark.cmd")
            self.assertEqual(dashboard_shim, bin_dir / "seam-dash.cmd")
            self.assertTrue(dashboard_shim.exists())
            content = dashboard_shim.read_text(encoding="ascii")
            self.assertIn("seam-dash.exe", content)
            self.assertIn("SEAM_DB_PATH", content)

    def test_install_repo_includes_dashboard_extra_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            install_root = root / "install"
            venv_dir = install_root / "runtime"
            bin_dir = install_root / "bin"
            (repo_root).mkdir(parents=True, exist_ok=True)
            layout = InstallLayout(
                repo_root=repo_root,
                install_root=install_root,
                venv_dir=venv_dir,
                bin_dir=bin_dir,
                seam_entry=venv_dir / "bin" / "seam",
                benchmark_entry=venv_dir / "bin" / "seam-benchmark",
                dashboard_entry=venv_dir / "bin" / "seam-dash",
                persistent_db_path=install_root / "state" / "seam.db",
                is_windows=False,
            )
            calls: list[list[str]] = []
            def _fake_run(cmd, check=True, **kwargs):  # pragma: no cover - test shim
                calls.append(list(cmd))
                class _Result:
                    returncode = 0
                return _Result()
            with patch("seam_runtime.installer.subprocess.run", side_effect=_fake_run):
                install_repo(layout, upgrade_pip=False)
            install_cmds = [call for call in calls if "install" in call]
            self.assertTrue(install_cmds)
            package_specs = [arg for call in install_cmds for arg in call if arg.endswith("[dash]")]
            self.assertTrue(package_specs, f"Expected a [dash] extra install in {install_cmds}")
            self.assertEqual(package_specs[0], f"{repo_root}[dash]")

    def test_install_repo_respects_include_dashboard_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            install_root = root / "install"
            venv_dir = install_root / "runtime"
            bin_dir = install_root / "bin"
            repo_root.mkdir(parents=True, exist_ok=True)
            layout = InstallLayout(
                repo_root=repo_root,
                install_root=install_root,
                venv_dir=venv_dir,
                bin_dir=bin_dir,
                seam_entry=venv_dir / "bin" / "seam",
                benchmark_entry=venv_dir / "bin" / "seam-benchmark",
                dashboard_entry=venv_dir / "bin" / "seam-dash",
                persistent_db_path=install_root / "state" / "seam.db",
                is_windows=False,
            )
            calls: list[list[str]] = []
            def _fake_run(cmd, check=True, **kwargs):  # pragma: no cover - test shim
                calls.append(list(cmd))
                class _Result:
                    returncode = 0
                return _Result()
            with patch("seam_runtime.installer.subprocess.run", side_effect=_fake_run):
                install_repo(layout, upgrade_pip=False, include_dashboard=False)
            for call in calls:
                for arg in call:
                    self.assertFalse(arg.endswith("[dash]"), f"Unexpected [dash] arg in {call}")


class PgVectorAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path(f"test_pgvector_{uuid4().hex}.db")
        self.model = HashEmbeddingModel()
        self.adapter = FakePgVectorAdapter(self.model)

    def tearDown(self) -> None:
        try:
            if self.db_path.exists():
                self.db_path.unlink()
        except PermissionError:
            pass

    def _make_batch(self):
        return compile_dsl(
            """
entity project "SEAM" as proj
claim c1:
  subject proj
  predicate supports
  object "databases"
claim c2:
  subject proj
  predicate supports
  object "context windows"
""",
            scope="project",
        )

    def test_pgvector_adapter_indexes_records(self) -> None:
        batch = self._make_batch()
        self.adapter.index_records(batch.records)
        indexable_count = sum(1 for r in batch.records if r.kind in INDEXABLE_KINDS)
        self.assertEqual(len(self.adapter._store), indexable_count)

    def test_pgvector_adapter_search_returns_scored_results(self) -> None:
        batch = self._make_batch()
        self.adapter.index_records(batch.records)
        scores = self.adapter.search("databases context windows", limit=5)
        self.assertGreater(len(scores), 0)
        for score in scores.values():
            self.assertIsInstance(score, float)
            self.assertGreater(score, 0.0)

    def test_pgvector_adapter_upsert_does_not_duplicate(self) -> None:
        batch = self._make_batch()
        self.adapter.index_records(batch.records)
        count_first = len(self.adapter._store)
        self.adapter.index_records(batch.records)
        self.assertEqual(len(self.adapter._store), count_first)

    def test_pgvector_adapter_schema_ddl_is_executed(self) -> None:
        batch = self._make_batch()
        self.adapter.index_records(batch.records)
        sql_lower = [s.lower() for s in self.adapter.sql_log]
        self.assertTrue(any("create extension" in s and "vector" in s for s in sql_lower))
        self.assertTrue(any("create table" in s and "seam_vector_index" in s for s in sql_lower))
        self.assertTrue(any("create index" in s and "seam_vector_index" in s for s in sql_lower))

    def test_runtime_uses_pgvector_adapter_when_dsn_provided(self) -> None:
        runtime = SeamRuntime(self.db_path, pgvector_dsn="postgresql://fake/db")
        self.assertIsInstance(runtime.vector_adapter, PgVectorAdapter)

    def test_runtime_picks_up_pgvector_dsn_from_env(self) -> None:
        old = os.environ.pop("SEAM_PGVECTOR_DSN", None)
        try:
            os.environ["SEAM_PGVECTOR_DSN"] = "postgresql://fake/db"
            runtime = SeamRuntime(self.db_path)
            self.assertIsInstance(runtime.vector_adapter, PgVectorAdapter)
        finally:
            if old is None:
                os.environ.pop("SEAM_PGVECTOR_DSN", None)
            else:
                os.environ["SEAM_PGVECTOR_DSN"] = old

    def test_runtime_persist_search_roundtrip_with_pgvector(self) -> None:
        runtime = SeamRuntime(self.db_path, vector_adapter=self.adapter)
        batch = runtime.compile_dsl(
            """
entity project "SEAM" as proj
claim c1:
  subject proj
  predicate supports
  object "databases"
claim c2:
  subject proj
  predicate supports
  object "context windows"
"""
        )
        runtime.persist_ir(batch)
        result = runtime.search_ir("databases context windows", budget=5)
        self.assertTrue(result.candidates)


class _FakePgCursor:
    def __init__(self, store: dict, sql_log: list) -> None:
        self._store = store
        self._sql_log = sql_log
        self._rows: list = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql: str, params=None) -> None:
        self._sql_log.append(sql.strip())
        sql_lower = sql.strip().lower()
        if sql_lower.startswith("insert") and params:
            record_id, model_name, dimension, source_text, source_hash, vec_literal, updated_at = params
            vec = [float(x) for x in vec_literal.strip("[]").split(",")]
            self._store[record_id] = {"model": model_name, "dim": dimension, "vec": vec, "source_hash": source_hash}
        elif sql_lower.startswith("select") and params:
            if "information_schema.columns" in sql_lower:
                self._rows = [("source_hash",)]
                return
            if "source_hash, dimension" in sql_lower:
                record_id, model_name = params
                entry = self._store.get(record_id)
                self._rows = [(entry["source_hash"], entry["dim"])] if entry and entry["model"] == model_name else []
                return
            vec_literal, model_name, dimension, _, limit = params
            query_vec = [float(x) for x in vec_literal.strip("[]").split(",")]
            scored = []
            for rid, entry in self._store.items():
                if entry["model"] != model_name or entry["dim"] != dimension:
                    continue
                score = cosine(query_vec, entry["vec"])
                if score > 0:
                    scored.append((rid, score))
            scored.sort(key=lambda item: -item[1])
            self._rows = scored[:limit]

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakePgConnection:
    def __init__(self, store: dict, sql_log: list) -> None:
        self._store = store
        self._sql_log = sql_log

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def cursor(self):
        return _FakePgCursor(self._store, self._sql_log)

    def commit(self):
        pass


class FakePgVectorAdapter(PgVectorAdapter):
    def __init__(self, model: HashEmbeddingModel) -> None:
        super().__init__(dsn="fake://", model=model)
        self._store: dict = {}
        self.sql_log: list[str] = []

    def _connect(self):
        return _FakePgConnection(self._store, self.sql_log)


class FakeChromaCollection:
    def __init__(self) -> None:
        self.entries: dict[str, dict[str, object]] = {}

    def upsert(self, ids, embeddings, documents, metadatas) -> None:
        for record_id, embedding, document, metadata in zip(ids, embeddings, documents, metadatas, strict=False):
            self.entries[record_id] = {
                "embedding": embedding,
                "document": document,
                "metadata": metadata,
            }

    def query(self, query_embeddings, n_results, include):
        query_embedding = query_embeddings[0]
        scored = []
        for record_id, payload in self.entries.items():
            similarity = cosine(query_embedding, payload["embedding"])
            distance = max(0.0, 1.0 - similarity)
            scored.append((record_id, distance, payload))
        scored.sort(key=lambda item: item[1])
        top = scored[:n_results]
        return {
            "ids": [[item[0] for item in top]],
            "distances": [[item[1] for item in top]],
            "documents": [[item[2]["document"] for item in top]],
            "metadatas": [[item[2]["metadata"] for item in top]],
        }


class FakeChromaClient:
    def __init__(self) -> None:
        self.collection = FakeChromaCollection()

    def get_or_create_collection(self, name, metadata=None):
        return self.collection


class LX1NotationTests(unittest.TestCase):
    """LX/1 compact AI-readable notation — encode/decode and token savings."""

    def _make_ent(self) -> "MIRLRecord":
        from seam_runtime.mirl import MIRLRecord, RecordKind, Status
        return MIRLRecord(
            id="ent:user:local",
            kind=RecordKind.ENT,
            ns="local.default",
            scope="project",
            attrs={"entity_type": "user", "label": "local_user"},
        )

    def _make_clm(self) -> "MIRLRecord":
        from seam_runtime.mirl import MIRLRecord, RecordKind, Status
        return MIRLRecord(
            id="clm:1",
            kind=RecordKind.CLM,
            ns="local.default",
            scope="project",
            conf=0.92,
            status=Status.ASSERTED,
            prov=["prov:compile:1"],
            evidence=["span:1"],
            attrs={"subject": "ent:project:seam", "predicate": "goal", "object": "build_memory_runtime"},
        )

    def _make_sta(self) -> "MIRLRecord":
        from seam_runtime.mirl import MIRLRecord, RecordKind
        return MIRLRecord(
            id="sta:ent:project:seam",
            kind=RecordKind.STA,
            ns="local.default",
            scope="project",
            conf=0.9,
            prov=["prov:compile:1"],
            evidence=["span:1"],
            attrs={"target": "ent:project:seam", "fields": {"goal": "build_memory_runtime", "scope": ["db", "rag"]}},
        )

    def _make_raw(self) -> "MIRLRecord":
        from seam_runtime.mirl import MIRLRecord, RecordKind, Status
        return MIRLRecord(
            id="raw:1",
            kind=RecordKind.RAW,
            ns="local.default",
            scope="project",
            status=Status.OBSERVED,
            attrs={"source_ref": "local://input", "content": "I want to build a memory runtime", "media_type": "text/plain"},
        )

    def test_encode_ent_omits_defaults(self) -> None:
        from seam_runtime.lx1 import encode_record
        line = encode_record(self._make_ent())
        self.assertTrue(line.startswith("E ent:user:local "))
        self.assertNotIn("local.default", line)
        self.assertNotIn("project", line)
        self.assertNotIn("asserted", line)
        self.assertIn("entity_type=user", line)
        self.assertIn("label=local_user", line)

    def test_roundtrip_ent(self) -> None:
        from seam_runtime.lx1 import decode_record, encode_record
        original = self._make_ent()
        line = encode_record(original)
        restored = decode_record(line)
        self.assertEqual(restored.id, original.id)
        self.assertEqual(restored.kind, original.kind)
        self.assertEqual(restored.attrs, original.attrs)
        self.assertAlmostEqual(restored.conf, original.conf)
        self.assertEqual(restored.status, original.status)

    def test_roundtrip_clm_with_meta(self) -> None:
        from seam_runtime.lx1 import decode_record, encode_record
        original = self._make_clm()
        line = encode_record(original)
        self.assertIn("~c=0.92", line)
        self.assertIn("~@prov:compile:1", line)
        self.assertIn("~^span:1", line)
        restored = decode_record(line)
        self.assertEqual(restored.id, original.id)
        self.assertEqual(restored.prov, original.prov)
        self.assertEqual(restored.evidence, original.evidence)
        self.assertAlmostEqual(restored.conf, 0.92)
        self.assertEqual(restored.attrs, original.attrs)

    def test_roundtrip_sta_with_nested_dict(self) -> None:
        from seam_runtime.lx1 import decode_record, encode_record
        original = self._make_sta()
        line = encode_record(original)
        restored = decode_record(line)
        self.assertEqual(restored.id, original.id)
        self.assertEqual(restored.attrs["target"], "ent:project:seam")
        fields = restored.attrs["fields"]
        self.assertEqual(fields["goal"], "build_memory_runtime")
        self.assertEqual(fields["scope"], ["db", "rag"])

    def test_roundtrip_raw_with_quoted_content(self) -> None:
        from seam_runtime.lx1 import decode_record, encode_record
        original = self._make_raw()
        line = encode_record(original)
        self.assertIn('content="I want to build a memory runtime"', line)
        restored = decode_record(line)
        self.assertEqual(restored.attrs["content"], "I want to build a memory runtime")
        self.assertEqual(restored.attrs["source_ref"], "local://input")
        self.assertEqual(restored.attrs["media_type"], "text/plain")

    def test_roundtrip_observed_status(self) -> None:
        from seam_runtime.lx1 import decode_record, encode_record
        from seam_runtime.mirl import Status
        original = self._make_raw()
        line = encode_record(original)
        self.assertIn("~s=o", line)
        restored = decode_record(line)
        self.assertEqual(restored.status, Status.OBSERVED)

    def test_batch_roundtrip(self) -> None:
        from seam_runtime.lx1 import decode, encode
        from seam_runtime.mirl import IRBatch
        batch = IRBatch([self._make_ent(), self._make_clm(), self._make_sta()])
        compact = encode(batch)
        self.assertTrue(compact.startswith("!LX1 "))
        restored = decode(compact)
        self.assertEqual(len(restored.records), 3)
        ids = {r.id for r in restored.records}
        self.assertIn("ent:user:local", ids)
        self.assertIn("clm:1", ids)
        self.assertIn("sta:ent:project:seam", ids)

    def test_token_savings_vs_verbose_mirl(self) -> None:
        from seam_runtime.lx1 import encode, token_savings_report
        from seam_runtime.mirl import IRBatch
        batch = IRBatch([self._make_ent(), self._make_clm(), self._make_sta(), self._make_raw()])
        verbose = batch.to_text()
        compact = encode(batch)
        report = token_savings_report(verbose, compact)
        self.assertGreater(report["token_savings_ratio"], 0.50,
                           "LX/1 should save >50% of tokens vs verbose MIRL JSON")
        self.assertGreater(report["intelligence_per_token_gain"], 2.0,
                           "LX/1 should deliver >2x intelligence per token vs verbose MIRL")

    def test_compile_nl_lx1_roundtrip(self) -> None:
        from seam_runtime.lx1 import decode, encode, token_savings_report
        runtime = SeamRuntime(":memory:")
        batch = runtime.compile_nl(
            "I want to build a durable memory runtime for AI that works without losing information."
        )
        verbose = batch.to_text()
        compact = encode(batch)
        report = token_savings_report(verbose, compact)
        self.assertGreater(report["token_savings_ratio"], 0.50)
        restored = decode(compact)
        original_ids = {r.id for r in batch.records}
        restored_ids = {r.id for r in restored.records}
        self.assertEqual(original_ids, restored_ids)

    def test_lx1_encode_cli_command(self) -> None:
        import tempfile
        runtime = SeamRuntime(":memory:")
        batch = runtime.compile_nl("SEAM stores knowledge efficiently.")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mirl", delete=False) as f:
            f.write(batch.to_text())
            mirl_path = f.name
        try:
            buf = StringIO()
            with redirect_stdout(buf):
                run_cli(["lx1-encode", mirl_path])
            output = buf.getvalue()
            self.assertIn("!LX1", output)
            self.assertIn("ns=local.default", output)
        finally:
            Path(mirl_path).unlink(missing_ok=True)

    def test_lx1_benchmark_cli_command(self) -> None:
        import tempfile
        runtime = SeamRuntime(":memory:")
        batch = runtime.compile_nl("SEAM stores knowledge efficiently.")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mirl", delete=False) as f:
            f.write(batch.to_text())
            mirl_path = f.name
        try:
            buf = StringIO()
            with redirect_stdout(buf):
                run_cli(["lx1-benchmark", mirl_path])
            output = buf.getvalue()
            self.assertIn("Token savings", output)
            self.assertIn("Intelligence/token", output)
        finally:
            Path(mirl_path).unlink(missing_ok=True)

    def test_reserved_token_strings_roundtrip(self) -> None:
        from seam_runtime.lx1 import decode_record, encode_record
        from seam_runtime.mirl import MIRLRecord, RecordKind
        record = MIRLRecord(
            id="ent:test",
            kind=RecordKind.ENT,
            attrs={"status_label": "true", "flag": "null", "active": "false"},
        )
        line = encode_record(record)
        restored = decode_record(line)
        self.assertEqual(restored.attrs["status_label"], "true")
        self.assertEqual(restored.attrs["flag"], "null")
        self.assertEqual(restored.attrs["active"], "false")

    def test_numeric_attr_types_roundtrip(self) -> None:
        from seam_runtime.lx1 import decode_record, encode_record
        from seam_runtime.mirl import MIRLRecord, RecordKind
        record = MIRLRecord(
            id="span:1",
            kind=RecordKind.SPAN,
            attrs={"start": 0, "end": 42, "score": 0.95},
        )
        line = encode_record(record)
        restored = decode_record(line)
        self.assertEqual(restored.attrs["start"], 0)
        self.assertEqual(restored.attrs["end"], 42)
        self.assertAlmostEqual(restored.attrs["score"], 0.95)


if __name__ == "__main__":
    unittest.main()

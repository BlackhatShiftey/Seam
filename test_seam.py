import json
import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from uuid import uuid4

from experimental.retrieval_orchestrator import ChromaSemanticAdapter, QueryIntent, RetrievalOrchestrator
from experimental.retrieval_orchestrator.adapters import SQLiteIRAdapter
from experimental.retrieval_orchestrator.planner import build_plan
from seam import SeamRuntime, compile_dsl, compile_nl, decompile_ir, load_ir_lines, pack_ir, render_ir, unpack_pack
from seam_runtime.cli import run_cli
from seam_runtime.dashboard import run_dashboard
from seam_runtime.installer import default_runtime_db_path, render_posix_shim, render_windows_cmd_shim
from seam_runtime.lossless import benchmark_text_lossless, compress_text_lossless, decompress_text_lossless
from seam_runtime.models import OpenAICompatibleEmbeddingModel, cosine, default_embedding_model
from seam_runtime.pack import score_pack, unpack_exact_pack
from seam_runtime.symbols import build_symbol_maps, namespace_chain
from seam_runtime.verify import verify_ir

try:
    from rich.console import Console
except ImportError:  # pragma: no cover - optional at import time
    Console = None


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

    def test_vector_index_reindex_and_search(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_nl("We need a translator back into natural language for memory workflows.")
        runtime.persist_ir(batch)
        reindex_report = runtime.reindex_vectors()
        self.assertIn("clm:2", reindex_report["indexed_ids"])
        result = runtime.search_ir("translator natural language", budget=3)
        top_ids = [candidate.record.id for candidate in result.candidates]
        self.assertIn("clm:2", top_ids)

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
            self.assertEqual(report["summary"]["family_count"], 6)
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
        self.assertIn("SEAM doctor: PASS", payload)
        self.assertIn("Compile smoke: PASS", payload)

    def test_cli_doctor_json_reports_dependency_status(self) -> None:
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli(["doctor", "--format", "json"])
        payload = stream.getvalue()
        self.assertIn('"status": "PASS"', payload)
        self.assertIn('"dependencies"', payload)

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

if __name__ == "__main__":
    unittest.main()


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

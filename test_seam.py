import os
import unittest
from pathlib import Path
from uuid import uuid4

from seam import SeamRuntime, compile_dsl, compile_nl, decompile_ir, load_ir_lines, pack_ir, render_ir, unpack_pack
from seam_runtime.models import OpenAICompatibleEmbeddingModel, default_embedding_model
from seam_runtime.pack import score_pack, unpack_exact_pack
from seam_runtime.symbols import build_symbol_maps, namespace_chain
from seam_runtime.verify import verify_ir


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
        pack = runtime.pack_ir(record_ids=[record.id for record in compact_batch.records if record.kind.value in {"CLM", "STA", "SYM"}], mode="context")
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


if __name__ == "__main__":
    unittest.main()

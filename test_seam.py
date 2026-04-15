import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from uuid import uuid4

from experimental.hybrid_orchestrator import ChromaSemanticAdapter, HybridOrchestrator, QueryIntent
from experimental.hybrid_orchestrator.planner import build_plan
from seam import SeamRuntime, compile_dsl, compile_nl, decompile_ir, load_ir_lines, pack_ir, render_ir, unpack_pack
from seam_runtime.cli import run_cli
from seam_runtime.models import cosine
from seam_runtime.pack import unpack_exact_pack
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

    def test_retrieval_orchestrator_builds_mixed_plan(self) -> None:
        runtime = SeamRuntime(self.db_path)
        orchestrator = HybridOrchestrator(runtime)
        plan = orchestrator.plan("kind:CLM translator natural language", scope="thread", budget=3)
        self.assertEqual(plan.intent, QueryIntent.HYBRID)
        self.assertEqual(plan.filters.kinds, ["CLM"])
        self.assertEqual([leg.name for leg in plan.legs], ["sql", "vector"])
        self.assertEqual(plan.normalized_query, "translator natural language")

    def test_retrieval_orchestrator_merges_sql_and_vector_legs(self) -> None:
        runtime = SeamRuntime(self.db_path)
        batch = runtime.compile_nl("We need a translator back into natural language for memory workflows.")
        runtime.persist_ir(batch)
        orchestrator = HybridOrchestrator(runtime)
        result = orchestrator.search("kind:CLM translator natural language", budget=3, include_trace=True)
        self.assertTrue(result.candidates)
        translator = next((candidate for candidate in result.candidates if candidate.record.id == "clm:2"), None)
        self.assertIsNotNone(translator)
        self.assertIn("sql", translator.sources)
        self.assertIsNotNone(result.trace)
        self.assertIn("sql", result.trace["legs"])
        self.assertIn("vector", result.trace["legs"])

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
        orchestrator = HybridOrchestrator(
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
        orchestrator = HybridOrchestrator(runtime)
        rag = orchestrator.rag("translator natural language", budget=3, pack_budget=10, include_trace=True)
        self.assertIn("clm:2", rag.candidate_ids)
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

    def test_cli_compile_nl_rag_sync_persists_and_syncs(self) -> None:
        stream = StringIO()
        with redirect_stdout(stream):
            run_cli([
                "--db",
                str(self.db_path),
                "compile-nl",
                "We need a translator back into natural language for memory workflows.",
                "--index",
            ])
        runtime = SeamRuntime(self.db_path)
        records = runtime.store.load_ir().records
        self.assertTrue(records)


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

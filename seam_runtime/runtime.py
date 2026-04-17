from __future__ import annotations

import json
import os
from pathlib import Path

from .benchmarks import run_benchmark_suite, verify_benchmark_bundle
from .dsl import compile_dsl
from .evals import run_retrieval_benchmark
from .mirl import Artifact, IRBatch, Pack, PersistReport, ReconcileReport, SearchResult, TraceGraph, VerifyReport
from .models import EmbeddingModel, default_embedding_model
from .nl import compile_nl
from .pack import pack_record, pack_records
from .reconcile import reconcile_ir
from .retrieval import search_batch
from .storage import SQLiteStore
from .symbols import export_symbol_markdown, propose_symbols
from .transpile import transpile_python
from .vector_adapters import PgVectorAdapter, SQLiteVectorAdapter, VectorAdapter
from .verify import verify_ir


class SeamRuntime:
    def __init__(
        self,
        store_path: str | Path = "seam.db",
        embedding_model: EmbeddingModel | None = None,
        vector_adapter: VectorAdapter | None = None,
        pgvector_dsn: str | None = None,
    ) -> None:
        self.store = SQLiteStore(store_path)
        self.embedding_model = embedding_model or default_embedding_model()
        resolved_dsn = pgvector_dsn or os.environ.get("SEAM_PGVECTOR_DSN")
        if vector_adapter is not None:
            self.vector_adapter = vector_adapter
        elif resolved_dsn:
            self.vector_adapter = PgVectorAdapter(resolved_dsn, self.embedding_model)
        else:
            self.vector_adapter = SQLiteVectorAdapter(str(store_path), self.embedding_model)

    def compile_nl(self, raw_text: str, source_ref: str = "local://input", ns: str = "local.default", scope: str = "thread") -> IRBatch:
        return compile_nl(raw_text, source_ref=source_ref, ns=ns, scope=scope)

    def compile_dsl(self, dsl_text: str, ns: str = "local.default", scope: str = "project") -> IRBatch:
        return compile_dsl(dsl_text, ns=ns, scope=scope)

    def verify_ir(self, ir_batch: IRBatch) -> VerifyReport:
        return verify_ir(ir_batch)

    def normalize_ir(self, ir_batch: IRBatch) -> IRBatch:
        return IRBatch(sorted(ir_batch.records, key=lambda record: record.id))

    def persist_ir(self, ir_batch: IRBatch) -> PersistReport:
        report = self.verify_ir(ir_batch)
        if not report.valid:
            raise ValueError(json.dumps(report.to_dict(), indent=2))
        normalized = self.normalize_ir(ir_batch)
        persist_report = self.store.persist_ir(normalized)
        self.vector_adapter.index_records(normalized.records)
        return persist_report

    def search_ir(self, query: str, lens: str = "general", scope: str | None = None, budget: int = 5) -> SearchResult:
        batch = self.store.load_ir(scope=scope)
        vector_scores = self.vector_adapter.search(query, limit=max(budget * 3, 10))
        namespace = batch.records[0].ns if batch.records else None
        return search_batch(batch, query=query, scope=scope, limit=budget, vector_scores=vector_scores, namespace=namespace)

    def pack_ir(self, record_ids: list[str] | None = None, lens: str = "general", budget: int = 512, profile: str = "default", mode: str = "context") -> Pack:
        batch = self.store.load_ir(ids=record_ids) if record_ids else self.store.load_ir()
        namespace = batch.records[0].ns if batch.records else None
        pack = pack_records(batch.records, lens=lens, budget=budget, mode=mode, profile=profile, namespace=namespace)
        pack_mirl = pack_record(pack, ns=batch.records[0].ns if batch.records else "local.default", scope=batch.records[0].scope if batch.records else "project")
        if mode == "exact":
            report = self.verify_ir(IRBatch(batch.records + [pack_mirl]))
            if not report.valid:
                raise ValueError(json.dumps(report.to_dict(), indent=2))
        self.store.persist_ir(IRBatch([pack_mirl]))
        return pack

    def decompile_ir(self, record_ids: list[str], mode: str = "expanded") -> str:
        batch = self.store.load_ir(ids=record_ids)
        claims = [record for record in batch.records if record.kind.value == "CLM"]
        states = [record for record in batch.records if record.kind.value == "STA"]
        if states:
            fields = states[0].attrs.get("fields", {})
            body = "; ".join(f"{key}={value}" for key, value in fields.items())
        elif claims:
            body = "; ".join(f"{record.attrs.get('subject')} {record.attrs.get('predicate')} {record.attrs.get('object')}" for record in claims)
        else:
            body = "No MIRL records available."
        return body if mode == "minimal" else f"MIRL summary: {body}"

    def trace(self, obj_id: str) -> TraceGraph:
        return self.store.trace(obj_id)

    def reconcile_ir(self, record_ids: list[str] | None = None) -> ReconcileReport:
        batch = self.store.load_ir(ids=record_ids) if record_ids else self.store.load_ir()
        report = reconcile_ir(batch)
        if report.added_records:
            self.store.persist_ir(IRBatch(report.added_records))
        return report

    def transpile_ir(self, record_ids: list[str], target: str = "python") -> Artifact:
        batch = self.store.load_ir(ids=record_ids)
        if target != "python":
            raise NotImplementedError(f"Unsupported target: {target}")
        return transpile_python(batch.records)

    def suggest_symbols(self, record_ids: list[str] | None = None) -> IRBatch:
        batch = self.store.load_ir(ids=record_ids) if record_ids else self.store.load_ir()
        return IRBatch(propose_symbols(batch))

    def promote_symbols(self, record_ids: list[str] | None = None, min_frequency: int = 2) -> PersistReport:
        batch = self.store.load_ir(ids=record_ids) if record_ids else self.store.load_ir()
        symbols = IRBatch(propose_symbols(batch, min_frequency=min_frequency))
        if not symbols.records:
            return PersistReport(stored_ids=[], store_path=self.store.path)
        return self.persist_ir(symbols)

    def export_symbols(self, namespace: str | None = None, output_path: str | Path | None = None) -> str:
        batch = self.store.load_ir(ns=namespace)
        markdown = export_symbol_markdown(batch.records, namespace=namespace)
        if output_path is not None:
            Path(output_path).write_text(markdown, encoding="utf-8")
        return markdown

    def run_retrieval_benchmark(self) -> dict[str, object]:
        return run_retrieval_benchmark(embedding_model=self.embedding_model)

    def run_benchmark_suite(
        self,
        suite: str = "all",
        tokenizer: str = "auto",
        min_token_savings: float = 0.30,
        persist: bool = False,
        include_machine_text: bool = False,
        bundle_path: str | Path | None = None,
    ) -> dict[str, object]:
        return run_benchmark_suite(
            self,
            suite=suite,
            tokenizer=tokenizer,
            min_token_savings=min_token_savings,
            persist=persist,
            include_machine_text=include_machine_text,
            bundle_path=bundle_path,
        )

    def verify_benchmark_bundle(self, bundle: str | Path | dict[str, object]) -> dict[str, object]:
        return verify_benchmark_bundle(bundle)

    def read_benchmark_run(self, run_id: str) -> dict[str, object]:
        return self.store.read_benchmark_run(run_id)

    def list_benchmark_runs(self, limit: int = 10) -> list[dict[str, object]]:
        return self.store.list_benchmark_runs(limit=limit)

    def reindex_vectors(self, record_ids: list[str] | None = None) -> dict[str, object]:
        batch = self.store.load_ir(ids=record_ids) if record_ids else self.store.load_ir()
        self.vector_adapter.index_records(batch.records)
        return {
            "indexed_ids": [record.id for record in batch.records],
            "model": self.embedding_model.name,
            "adapter": getattr(self.vector_adapter, "name", "unknown"),
        }

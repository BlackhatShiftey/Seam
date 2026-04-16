from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from seam_runtime.mirl import IRBatch, MIRLRecord, iter_textual_fields
from seam_runtime.models import EmbeddingModel
from seam_runtime.storage import SQLiteStore
from seam_runtime.vector import INDEXABLE_KINDS, SQLiteVectorIndex
from seam_runtime.vector_adapters import VectorAdapter

from .types import LegHit, RetrievalPlan


class SQLAdapter(Protocol):
    def search(self, plan: RetrievalPlan, limit: int) -> list[LegHit]:
        ...


class SemanticAdapter(Protocol):
    def search(self, plan: RetrievalPlan, limit: int) -> list[LegHit]:
        ...


class SQLiteIRAdapter:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def search(self, plan: RetrievalPlan, limit: int) -> list[LegHit]:
        ids = plan.filters.ids or None
        batch = self.store.load_ir(ids=ids, ns=plan.filters.namespace, scope=plan.filters.scope)
        query_tokens = _tokens(plan.normalized_query or plan.query)
        hits: list[LegHit] = []
        for record in batch.records:
            if not plan.filters.matches(record):
                continue
            lexical = _lexical_score(record, query_tokens)
            filter_bonus, reasons = _structured_reasons(record, plan)
            score = lexical + filter_bonus
            if score <= 0:
                continue
            hits.append(LegHit(leg="sql", record=record, score=score, reasons=reasons + [f"lexical={lexical:.2f}"]))
        return sorted(hits, key=lambda item: item.score, reverse=True)[:limit]


class SeamVectorSearchAdapter:
    def __init__(self, store: SQLiteStore, vector_adapter: VectorAdapter) -> None:
        self.store = store
        self.vector_adapter = vector_adapter

    def search(self, plan: RetrievalPlan, limit: int) -> list[LegHit]:
        query_text = plan.normalized_query or plan.query
        if not query_text.strip():
            return []
        raw_scores = self.vector_adapter.search(query_text, limit=max(limit * 3, 10))
        if not raw_scores:
            return []
        batch = self.store.load_ir(ids=list(raw_scores))
        by_id = batch.by_id()
        hits: list[LegHit] = []
        for record_id, raw_score in raw_scores.items():
            record = by_id.get(record_id)
            if record is None or not plan.filters.matches(record):
                continue
            if plan.filters.active():
                raw_score += 0.05 * _matched_filter_count(record, plan)
            hits.append(LegHit(leg="vector", record=record, score=raw_score, reasons=[f"semantic={raw_score:.2f}"]))
        return sorted(hits, key=lambda item: item.score, reverse=True)[:limit]


@dataclass
class ChromaSemanticAdapter:
    store: SQLiteStore
    embedding_model: EmbeddingModel
    persist_directory: str = ".seam_chroma"
    collection_name: str = "seam_hybrid"
    client: object | None = None
    sync_on_search: bool = True

    def _client(self):
        if self.client is not None:
            return self.client
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is not installed. Install it to use --semantic-backend chroma.") from exc
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        return self.client

    def _collection(self):
        return self._client().get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def sync_records(self, plan: RetrievalPlan | None = None) -> int:
        ids = plan.filters.ids or None if plan is not None else None
        namespace = plan.filters.namespace if plan is not None else None
        scope = plan.filters.scope if plan is not None else None
        batch = self.store.load_ir(ids=ids, ns=namespace, scope=scope)
        return self.sync_batch(batch)

    def sync_batch(self, batch: IRBatch) -> int:
        records = [record for record in batch.records if record.kind in INDEXABLE_KINDS]
        if not records:
            return 0
        collection = self._collection()
        rendered = [SQLiteVectorIndex.render_record_text(record) for record in records]
        collection.upsert(
            ids=[record.id for record in records],
            embeddings=[self.embedding_model.embed(text) for text in rendered],
            documents=rendered,
            metadatas=[_chroma_metadata(record) for record in records],
        )
        return len(records)

    def search(self, plan: RetrievalPlan, limit: int) -> list[LegHit]:
        query_text = plan.normalized_query or plan.query
        if not query_text.strip():
            return []
        if self.sync_on_search:
            self.sync_records(plan)
        collection = self._collection()
        response = collection.query(
            query_embeddings=[self.embedding_model.embed(query_text)],
            n_results=max(limit * 3, 10),
            include=["metadatas", "distances", "documents"],
        )
        ids = response.get("ids", [[]])[0]
        distances = response.get("distances", [[]])[0]
        if not ids:
            return []
        batch = self.store.load_ir(ids=list(ids))
        by_id = batch.by_id()
        hits: list[LegHit] = []
        for index, record_id in enumerate(ids):
            record = by_id.get(record_id)
            if record is None or not plan.filters.matches(record):
                continue
            distance = float(distances[index]) if index < len(distances) else 1.0
            score = max(0.0, 1.0 - distance)
            if plan.filters.active():
                score += 0.05 * _matched_filter_count(record, plan)
            hits.append(LegHit(leg="chroma", record=record, score=score, reasons=[f"chroma={score:.2f}"]))
        return sorted(hits, key=lambda item: item.score, reverse=True)[:limit]


def _structured_reasons(record: MIRLRecord, plan: RetrievalPlan) -> tuple[float, list[str]]:
    bonus = 0.0
    reasons: list[str] = []
    if plan.filters.ids and record.id in plan.filters.ids:
        bonus += 1.2
        reasons.append("matched=id")
    if plan.filters.kinds and record.kind.value in plan.filters.kinds:
        bonus += 0.8
        reasons.append("matched=kind")
    if plan.filters.namespace and record.ns == plan.filters.namespace:
        bonus += 0.4
        reasons.append("matched=ns")
    if plan.filters.scope and record.scope == plan.filters.scope:
        bonus += 0.4
        reasons.append("matched=scope")
    if plan.filters.predicate and str(record.attrs.get("predicate", "")).lower() == plan.filters.predicate.lower():
        bonus += 0.6
        reasons.append("matched=predicate")
    if plan.filters.subject and str(record.attrs.get("subject", "")).lower() == plan.filters.subject.lower():
        bonus += 0.6
        reasons.append("matched=subject")
    if plan.filters.object_text and plan.filters.object_text.lower() in str(record.attrs.get("object", "")).lower():
        bonus += 0.6
        reasons.append("matched=object")
    return bonus, reasons


def _matched_filter_count(record: MIRLRecord, plan: RetrievalPlan) -> int:
    matched = 0
    if plan.filters.ids and record.id in plan.filters.ids:
        matched += 1
    if plan.filters.kinds and record.kind.value in plan.filters.kinds:
        matched += 1
    if plan.filters.namespace and record.ns == plan.filters.namespace:
        matched += 1
    if plan.filters.scope and record.scope == plan.filters.scope:
        matched += 1
    if plan.filters.predicate and str(record.attrs.get("predicate", "")).lower() == plan.filters.predicate.lower():
        matched += 1
    if plan.filters.subject and str(record.attrs.get("subject", "")).lower() == plan.filters.subject.lower():
        matched += 1
    if plan.filters.object_text and plan.filters.object_text.lower() in str(record.attrs.get("object", "")).lower():
        matched += 1
    return matched


def _lexical_score(record: MIRLRecord, query_tokens: list[str]) -> float:
    if not query_tokens:
        return 0.0
    record_tokens = set(_tokens(" ".join(iter_textual_fields(record))))
    if not record_tokens:
        return 0.0
    return len(set(query_tokens) & record_tokens) / max(len(set(query_tokens)), 1)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_:-]+", text.lower())


def _chroma_metadata(record: MIRLRecord) -> dict[str, str]:
    attrs = record.attrs
    metadata = {
        "kind": record.kind.value,
        "ns": record.ns,
        "scope": record.scope,
    }
    if "predicate" in attrs:
        metadata["predicate"] = str(attrs.get("predicate"))
    if "subject" in attrs:
        metadata["subject"] = str(attrs.get("subject"))
    if "object" in attrs:
        metadata["object"] = str(attrs.get("object"))
    return metadata

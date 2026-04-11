from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable

from .mirl import IRBatch, MIRLRecord, RecordKind, SearchCandidate, SearchResult, cosine_similarity, iter_textual_fields
from .symbols import build_symbol_maps


def search_batch(batch: IRBatch, query: str, scope: str | None = None, limit: int = 5, vector_scores: dict[str, float] | None = None, namespace: str | None = None) -> SearchResult:
    _, symbol_to_expansion = build_symbol_maps(batch.records, namespace=namespace)
    expanded_query = _expand_query(query, symbol_to_expansion)
    tokens = _tokens(expanded_query)
    query_vector = Counter(tokens)
    batch_by_id = batch.by_id()
    records = [record for record in batch.records if scope is None or record.scope == scope]
    graph = _graph(records)
    candidates: list[SearchCandidate] = []
    vector_scores = vector_scores or {}

    for record in records:
        if record.kind not in {RecordKind.CLM, RecordKind.STA, RecordKind.EVT, RecordKind.REL}:
            continue
        lexical = _lexical_score(record, tokens)
        semantic = vector_scores.get(record.id, _semantic_score(record, query_vector))
        graph_bonus = _graph_score(record, tokens, graph)
        temporal = _temporal_score(record)
        score = (0.4 * lexical) + (0.35 * semantic) + (0.15 * graph_bonus) + (0.10 * temporal)
        if score <= 0:
            continue
        evidence = [batch_by_id[ev] for ev in record.evidence if ev in batch_by_id]
        reasons = [f"lexical={lexical:.2f}", f"semantic={semantic:.2f}", f"graph={graph_bonus:.2f}", f"temporal={temporal:.2f}"]
        candidates.append(SearchCandidate(record=record, score=score, reasons=reasons, evidence=evidence))

    return SearchResult(query=expanded_query, candidates=sorted(candidates, key=lambda item: item.score, reverse=True)[:limit])


def raw_search(records: Iterable[MIRLRecord], query: str, limit: int = 5) -> SearchResult:
    tokens = _tokens(query)
    candidates: list[SearchCandidate] = []
    for record in records:
        if record.kind != RecordKind.RAW:
            continue
        content = str(record.attrs.get("content", ""))
        overlap = len(set(tokens) & set(_tokens(content)))
        if overlap == 0:
            continue
        candidates.append(SearchCandidate(record=record, score=float(overlap), reasons=[f"raw_overlap={overlap}"]))
    return SearchResult(query=query, candidates=sorted(candidates, key=lambda item: item.score, reverse=True)[:limit])


def _graph(records: list[MIRLRecord]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.kind == RecordKind.REL:
            src = str(record.attrs.get("src"))
            dst = str(record.attrs.get("dst"))
            graph[src].add(dst)
            graph[dst].add(src)
        elif record.kind == RecordKind.CLM:
            subject = str(record.attrs.get("subject"))
            obj = record.attrs.get("object")
            if isinstance(obj, str) and obj.startswith(("ent:", "clm:", "evt:", "sta:", "sym:")):
                graph[subject].add(obj)
                graph[obj].add(subject)
    return graph


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_:-]+", text.lower())


def _lexical_score(record: MIRLRecord, query_tokens: list[str]) -> float:
    record_tokens = set(_tokens(" ".join(iter_textual_fields(record))))
    if not record_tokens:
        return 0.0
    return len(set(query_tokens) & record_tokens) / max(len(set(query_tokens)), 1)


def _semantic_score(record: MIRLRecord, query_vector: Counter[str]) -> float:
    record_vector = Counter(_tokens(" ".join(iter_textual_fields(record))))
    return cosine_similarity(dict(query_vector), dict(record_vector))


def _graph_score(record: MIRLRecord, query_tokens: list[str], graph: dict[str, set[str]]) -> float:
    neighbors = graph.get(record.id, set())
    if not neighbors:
        return 0.0
    matched = sum(1 for neighbor in neighbors if any(token in neighbor.lower() for token in query_tokens))
    return matched / max(len(neighbors), 1)


def _temporal_score(record: MIRLRecord) -> float:
    return 1.0 if record.t0 else 0.2


def _expand_query(query: str, symbol_to_expansion: dict[str, str]) -> str:
    parts = []
    for token in query.split():
        parts.append(symbol_to_expansion.get(token, token))
    return " ".join(parts)

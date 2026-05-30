from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping

from .bm25 import BM25Index
from .mirl import IRBatch, MIRLRecord, RecordKind, SearchCandidate, SearchResult, cosine_similarity, iter_textual_fields
from .symbols import build_symbol_maps
from .temporal import parse_iso, temporal_distance_score


@dataclass(frozen=True)
class RetrievalFlags:
    """Audit #3 retrieval-scoring levers, all OFF by default.

    With every field at its default the scoring path is byte-identical to the
    pre-audit weighted-sum fusion, so flag-off runs reproduce the locked
    baseline exactly. Each lever is independent so it can be ablated alone or
    cumulatively. Read from the environment via ``retrieval_flags_from_env``.
    """

    # P0-1: when a real vector backend is active (vector_scores is non-empty)
    # but a record is absent from the semantic top-K, treat its semantic score
    # as 0.0 instead of falling back to bag-of-words cosine (which double-counts
    # lexical signal). No effect when vector_scores is empty (local/test path).
    semantic_zero_no_vector: bool = False
    # P0-2: apply the BM25 lexical signal to every candidate kind, not just RAW.
    bm25_all_kinds: bool = False
    # P1-1: fuse the four channels with Reciprocal Rank Fusion instead of the
    # fixed weighted sum. ``rrf_k`` is a principled constant, not a tuned knob.
    fusion: str = "weighted"  # "weighted" | "rrf"
    rrf_k: int = 60


def retrieval_flags_from_env(env: Mapping[str, str] | None = None) -> RetrievalFlags:
    env = os.environ if env is None else env

    def _on(name: str) -> bool:
        return env.get(name, "").strip().lower() in {"1", "true", "yes", "on"}

    return RetrievalFlags(
        semantic_zero_no_vector=_on("SEAM_RETRIEVAL_SEMANTIC_ZERO"),
        bm25_all_kinds=_on("SEAM_RETRIEVAL_BM25_ALL"),
        fusion="rrf" if _on("SEAM_RETRIEVAL_RRF") else "weighted",
    )


_WEIGHTS = (("lexical", 0.4), ("semantic", 0.35), ("graph", 0.15), ("temporal", 0.10))


def search_batch(batch: IRBatch, query: str, scope: str | None = None, limit: int = 5, vector_scores: dict[str, float] | None = None, namespace: str | None = None, include_raw: bool = False, bm25_index: BM25Index | None = None, temporal_window: tuple[datetime, datetime] | None = None, temporal_reference: datetime | None = None, flags: RetrievalFlags | None = None) -> SearchResult:
    flags = flags or RetrievalFlags()
    _, symbol_to_expansion = build_symbol_maps(batch.records, namespace=namespace)
    expanded_query = _expand_query(query, symbol_to_expansion)
    tokens = _tokens(expanded_query)
    query_vector = Counter(tokens)
    batch_by_id = batch.by_id()
    records = [record for record in batch.records if scope is None or record.scope == scope]
    graph = _graph(records)
    vector_scores = vector_scores or {}

    candidate_kinds = {RecordKind.CLM, RecordKind.STA, RecordKind.EVT, RecordKind.REL}
    if include_raw:
        candidate_kinds = candidate_kinds | {RecordKind.RAW}
    bm25_scores: dict[str, float] = bm25_index.score(query) if bm25_index else {}
    max_bm25 = max(bm25_scores.values()) if bm25_scores else 1.0

    # First pass: per-channel scores for every candidate record.
    scored: list[tuple[MIRLRecord, dict[str, float]]] = []
    for record in records:
        if record.kind not in candidate_kinds:
            continue
        lexical = _lexical_score(record, tokens)
        bm25_applies = record.id in bm25_scores and (flags.bm25_all_kinds or record.kind == RecordKind.RAW)
        if bm25_applies:
            lexical = max(lexical, bm25_scores[record.id] / max(max_bm25, 1.0))
        if record.id in vector_scores:
            semantic = vector_scores[record.id]
        elif flags.semantic_zero_no_vector and vector_scores:
            semantic = 0.0
        else:
            semantic = _semantic_score(record, query_vector)
        graph_bonus = _graph_score(record, tokens, graph)
        if temporal_reference is not None:
            temporal = temporal_distance_score(temporal_reference, parse_iso(record.t0))
        elif temporal_window is not None:
            t0_parsed = parse_iso(record.t0)
            if t0_parsed and temporal_window[0] <= t0_parsed <= temporal_window[1]:
                temporal = 1.0
            else:
                temporal = 0.0
        else:
            temporal = _temporal_score(record)
        scored.append((record, {"lexical": lexical, "semantic": semantic, "graph": graph_bonus, "temporal": temporal}))

    if flags.fusion == "rrf":
        candidates = _fuse_rrf(scored, batch_by_id, k=flags.rrf_k)
    else:
        candidates = _fuse_weighted(scored, batch_by_id)

    return SearchResult(query=expanded_query, candidates=sorted(candidates, key=lambda item: item.score, reverse=True)[:limit])


def _reasons(channels: dict[str, float]) -> list[str]:
    return [f"{name}={channels[name]:.2f}" for name, _ in _WEIGHTS]


def _fuse_weighted(scored: list[tuple[MIRLRecord, dict[str, float]]], batch_by_id: dict[str, MIRLRecord]) -> list[SearchCandidate]:
    candidates: list[SearchCandidate] = []
    for record, channels in scored:
        score = sum(weight * channels[name] for name, weight in _WEIGHTS)
        if score <= 0:
            continue
        evidence = [batch_by_id[ev] for ev in record.evidence if ev in batch_by_id]
        candidates.append(SearchCandidate(record=record, score=score, reasons=_reasons(channels), evidence=evidence))
    return candidates


def _fuse_rrf(scored: list[tuple[MIRLRecord, dict[str, float]]], batch_by_id: dict[str, MIRLRecord], k: int) -> list[SearchCandidate]:
    # Per-channel descending rank; only records with a positive channel score
    # participate in that channel. RRF score = sum_c 1/(k + rank_c).
    rrf: dict[str, float] = defaultdict(float)
    for name, _ in _WEIGHTS:
        ranked = sorted(
            ((channels[name], record) for record, channels in scored if channels[name] > 0),
            key=lambda pair: pair[0],
            reverse=True,
        )
        for rank, (_score, record) in enumerate(ranked):
            rrf[record.id] += 1.0 / (k + rank)
    candidates: list[SearchCandidate] = []
    for record, channels in scored:
        score = rrf.get(record.id, 0.0)
        if score <= 0:
            continue
        evidence = [batch_by_id[ev] for ev in record.evidence if ev in batch_by_id]
        candidates.append(SearchCandidate(record=record, score=score, reasons=_reasons(channels), evidence=evidence))
    return candidates


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

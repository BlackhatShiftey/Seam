from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dsl import compile_dsl
from .models import EmbeddingModel, HashEmbeddingModel, cosine
from .pack import pack_records, score_pack
from .retrieval import raw_search, search_batch
from .vector import INDEXABLE_KINDS, SQLiteVectorIndex


FIXTURE_PATH = Path(__file__).resolve().parent.parent / "docs" / "retrieval_gold_fixtures.json"


@dataclass(frozen=True)
class RetrievalFixture:
    name: str
    category: str
    format: str
    source: str
    query: str
    expected_ids: list[str]
    rejected_ids: list[str]
    budget: int = 5
    pack_budget: int = 96
    scope: str | None = None
    notes: str = ""


def default_retrieval_fixtures(path: str | Path | None = None) -> list[RetrievalFixture]:
    fixture_path = Path(path) if path is not None else FIXTURE_PATH
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return [
        RetrievalFixture(
            name=item["name"],
            category=item["category"],
            format=item.get("format", "dsl"),
            source=item["source"],
            query=item["query"],
            expected_ids=list(item["expected_ids"]),
            rejected_ids=list(item.get("rejected_ids", [])),
            budget=int(item.get("budget", 5)),
            pack_budget=int(item.get("pack_budget", 96)),
            scope=item.get("scope"),
            notes=item.get("notes", ""),
        )
        for item in payload
    ]


def run_retrieval_benchmark(fixtures: list[RetrievalFixture] | None = None, embedding_model: EmbeddingModel | None = None) -> dict[str, Any]:
    fixtures = fixtures or default_retrieval_fixtures()
    model = embedding_model or HashEmbeddingModel()
    results: list[dict[str, Any]] = []

    for fixture in fixtures:
        batch = _compile_fixture_batch(fixture)
        namespace = _benchmark_namespace(batch)
        scoped_records = [record for record in batch.records if fixture.scope is None or record.scope == fixture.scope]
        vector_scores = _vector_scores(scoped_records, fixture.query, model)
        raw_candidates = raw_search(scoped_records, fixture.query, limit=fixture.budget).candidates
        mirl_candidates = search_batch(batch, fixture.query, scope=fixture.scope, limit=fixture.budget, vector_scores={}, namespace=namespace).candidates
        hybrid_candidates = search_batch(batch, fixture.query, scope=fixture.scope, limit=fixture.budget, vector_scores=vector_scores, namespace=namespace).candidates
        vector_ranked_ids = _rank_vector_only(vector_scores, limit=fixture.budget)

        packs = {}
        pack_records_source = scoped_records if scoped_records else batch.records
        for mode in ("exact", "context", "narrative"):
            pack = pack_records(pack_records_source, lens=fixture.category, budget=fixture.pack_budget, mode=mode, namespace=namespace)
            packs[mode] = score_pack(pack, pack_records_source)

        results.append(
            {
                "name": fixture.name,
                "category": fixture.category,
                "query": fixture.query,
                "scope": fixture.scope,
                "expected_ids": fixture.expected_ids,
                "rejected_ids": fixture.rejected_ids,
                "notes": fixture.notes,
                "tracks": {
                    "raw": _track_report([candidate.record.id for candidate in raw_candidates], fixture.expected_ids, fixture.rejected_ids),
                    "vector": _track_report(vector_ranked_ids, fixture.expected_ids, fixture.rejected_ids),
                    "mirl": _track_report([candidate.record.id for candidate in mirl_candidates], fixture.expected_ids, fixture.rejected_ids),
                    "hybrid": _track_report([candidate.record.id for candidate in hybrid_candidates], fixture.expected_ids, fixture.rejected_ids),
                },
                "packs": packs,
            }
        )

    return {
        "summary": {
            "fixture_count": len(results),
            "embedding_model": model.name,
            "category_counts": _category_counts(results),
            "tracks": {track: _aggregate_track(results, track) for track in ("raw", "vector", "mirl", "hybrid")},
            "packs": {mode: _aggregate_pack(results, mode) for mode in ("exact", "context", "narrative")},
            "success_checks": {
                "mirl_beats_raw_on_fact_or_relation": any(_beats(result, "mirl", "raw") and result["category"] in {"fact", "relation"} for result in results),
                "hybrid_matches_or_beats_vector_on_relation": all(_matches_or_beats(result, "hybrid", "vector") for result in results if result["category"] == "relation"),
                "expected_over_rejected_on_temporal_scope_contradiction": all(_expected_beats_rejected(result, "hybrid") for result in results if result["rejected_ids"]),
                "exact_packs_reversible": all(result["packs"]["exact"]["reversibility"] == 1.0 for result in results),
                "context_packs_traceable": all(result["packs"]["context"]["traceability"] >= 0.66 for result in results),
            },
        },
        "fixtures": results,
    }


def _compile_fixture_batch(fixture: RetrievalFixture):
    if fixture.format != "dsl":
        raise ValueError(f"Unsupported fixture format: {fixture.format}")
    return compile_dsl(fixture.source, scope="project")


def _benchmark_namespace(batch) -> str | None:
    namespaces = sorted({record.ns for record in batch.records if record.ns})
    if not namespaces:
        return None
    return max(namespaces, key=lambda item: len(item.split(".")))


def _vector_scores(records, query: str, model: EmbeddingModel) -> dict[str, float]:
    query_vector = model.embed(query)
    scores: dict[str, float] = {}
    for record in records:
        if record.kind not in INDEXABLE_KINDS:
            continue
        record_vector = model.embed(SQLiteVectorIndex.render_record_text(record))
        score = cosine(query_vector, record_vector)
        if score > 0:
            scores[record.id] = score
    return scores


def _rank_vector_only(scores: dict[str, float], limit: int) -> list[str]:
    return [record_id for record_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]]


def _track_report(ranked_ids: list[str], expected_ids: list[str], rejected_ids: list[str]) -> dict[str, Any]:
    first_relevant_rank = next((index for index, record_id in enumerate(ranked_ids, start=1) if record_id in expected_ids), None)
    first_rejected_rank = next((index for index, record_id in enumerate(ranked_ids, start=1) if record_id in rejected_ids), None)
    reciprocal_rank = 0.0 if first_relevant_rank is None else 1.0 / first_relevant_rank
    relevant_hits = len([record_id for record_id in ranked_ids if record_id in expected_ids])
    rejected_hits = len([record_id for record_id in ranked_ids if record_id in rejected_ids])
    recall_at_k = relevant_hits / max(len(expected_ids), 1)
    rejection_rate = rejected_hits / max(len(rejected_ids), 1) if rejected_ids else 0.0
    clean_top1 = not ranked_ids or ranked_ids[0] not in rejected_ids
    return {
        "ranked_ids": ranked_ids,
        "hit": first_relevant_rank is not None,
        "first_relevant_rank": first_relevant_rank,
        "first_rejected_rank": first_rejected_rank,
        "relevant_hits": relevant_hits,
        "rejected_hits": rejected_hits,
        "recall_at_k": round(recall_at_k, 6),
        "rejection_rate": round(rejection_rate, 6),
        "clean_top1": clean_top1,
        "reciprocal_rank": round(reciprocal_rank, 6),
    }


def _aggregate_track(results: list[dict[str, Any]], track: str) -> dict[str, float]:
    if not results:
        return {"hit_rate": 0.0, "mrr": 0.0, "recall_at_k": 0.0, "rejection_rate": 0.0}
    hits = [1.0 if item["tracks"][track]["hit"] else 0.0 for item in results]
    reciprocal_ranks = [item["tracks"][track]["reciprocal_rank"] for item in results]
    recall_scores = [item["tracks"][track]["recall_at_k"] for item in results]
    rejection_scores = [item["tracks"][track]["rejection_rate"] for item in results if item["rejected_ids"]]
    return {
        "hit_rate": round(sum(hits) / len(hits), 6),
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 6),
        "recall_at_k": round(sum(recall_scores) / len(recall_scores), 6),
        "rejection_rate": round(sum(rejection_scores) / len(rejection_scores), 6) if rejection_scores else 0.0,
    }


def _aggregate_pack(results: list[dict[str, Any]], mode: str) -> dict[str, float]:
    if not results:
        return {"overall": 0.0, "compression_ratio": 0.0, "traceability": 0.0}
    overall = [item["packs"][mode]["overall"] for item in results]
    compression = [item["packs"][mode]["compression_ratio"] for item in results]
    traceability = [item["packs"][mode]["traceability"] for item in results]
    return {
        "overall": round(sum(overall) / len(overall), 6),
        "compression_ratio": round(sum(compression) / len(compression), 6),
        "traceability": round(sum(traceability) / len(traceability), 6),
    }


def _category_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result["category"]] = counts.get(result["category"], 0) + 1
    return counts


def _beats(result: dict[str, Any], winner: str, loser: str) -> bool:
    winner_track = result["tracks"][winner]
    loser_track = result["tracks"][loser]
    return (winner_track["recall_at_k"], winner_track["reciprocal_rank"], -winner_track["rejection_rate"]) > (
        loser_track["recall_at_k"],
        loser_track["reciprocal_rank"],
        -loser_track["rejection_rate"],
    )


def _matches_or_beats(result: dict[str, Any], winner: str, loser: str) -> bool:
    winner_track = result["tracks"][winner]
    loser_track = result["tracks"][loser]
    return (winner_track["recall_at_k"], winner_track["reciprocal_rank"], -winner_track["rejection_rate"]) >= (
        loser_track["recall_at_k"],
        loser_track["reciprocal_rank"],
        -loser_track["rejection_rate"],
    )


def _expected_beats_rejected(result: dict[str, Any], track: str) -> bool:
    candidate_track = result["tracks"][track]
    expected_rank = candidate_track["first_relevant_rank"]
    rejected_rank = candidate_track["first_rejected_rank"]
    if rejected_rank is None:
        return True
    if expected_rank is None:
        return False
    return expected_rank < rejected_rank and candidate_track["clean_top1"]

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mirl import IRBatch
from .retrieval import raw_search, search_batch


@dataclass
class RetrievalFixture:
    query: str
    expected_ids: list[str]


def default_retrieval_fixtures() -> list[RetrievalFixture]:
    return [
        RetrievalFixture(query="memory language databases rag", expected_ids=["clm:1", "sta:ent:project:seam"]),
        RetrievalFixture(query="translator natural language", expected_ids=["clm:4"]),
    ]


def run_retrieval_benchmark(batch: IRBatch, fixtures: list[RetrievalFixture] | None = None) -> dict[str, Any]:
    fixtures = fixtures or default_retrieval_fixtures()
    results: list[dict[str, Any]] = []
    for fixture in fixtures:
        raw_candidates = raw_search(batch.records, fixture.query, limit=5).candidates
        mirl_candidates = search_batch(batch, fixture.query, limit=5).candidates
        results.append(
            {
                "query": fixture.query,
                "expected_ids": fixture.expected_ids,
                "raw_hit": any(candidate.record.id in fixture.expected_ids for candidate in raw_candidates),
                "mirl_hit": any(candidate.record.id in fixture.expected_ids for candidate in mirl_candidates),
                "raw_candidates": [candidate.record.id for candidate in raw_candidates],
                "mirl_candidates": [candidate.record.id for candidate in mirl_candidates],
            }
        )
    return {"fixtures": results}

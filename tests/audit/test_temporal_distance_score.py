from __future__ import annotations

from datetime import datetime, timedelta

from seam_runtime.mirl import IRBatch, MIRLRecord, RecordKind, Status
from seam_runtime.retrieval import search_batch
from seam_runtime.temporal import (
    parse_temporal_reference,
    temporal_distance_score,
)


def test_temporal_distance_score_decays_monotonically_from_question_reference() -> None:
    anchor = datetime(2024, 1, 1)
    ref = parse_temporal_reference("what happened three weeks ago?", anchor=anchor)
    assert ref == datetime(2023, 12, 11)

    candidate_offsets = [21, 30, 60, 180, 365]
    scores = [
        temporal_distance_score(ref, anchor - timedelta(days=days))
        for days in candidate_offsets
    ]

    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 1.0
    assert scores[-1] < scores[0]


def test_temporal_distance_score_returns_zero_without_question_reference() -> None:
    anchor = datetime(2024, 1, 1)

    ref = parse_temporal_reference("what did Alice mention?", anchor=anchor)

    assert ref is None
    assert temporal_distance_score(ref, anchor) == 0.0


def test_temporal_distance_score_returns_zero_without_candidate_timestamp() -> None:
    anchor = datetime(2024, 1, 1)
    ref = parse_temporal_reference("what happened yesterday?", anchor=anchor)

    assert ref == datetime(2023, 12, 31)
    assert temporal_distance_score(ref, None) == 0.0


def test_temporal_reference_retrieval_prefers_nearest_candidate_without_weight_change() -> None:
    anchor = datetime(2024, 1, 1)
    ref = parse_temporal_reference("what happened three weeks ago?", anchor=anchor)
    assert ref is not None
    batch = IRBatch(
        [
            _event("evt:near", "Alice mentioned an event", "2023-12-11"),
            _event("evt:far", "Alice mentioned an event", "2023-07-01"),
        ]
    )

    result = search_batch(
        batch,
        query="what event did Alice mention?",
        temporal_reference=ref,
        limit=2,
    )

    assert [candidate.record.id for candidate in result.candidates] == [
        "evt:near",
        "evt:far",
    ]
    assert "temporal=1.00" in result.candidates[0].reasons


def test_locomo_adapter_builds_temporal_reference_from_scope_anchor() -> None:
    from benchmarks.external.locomo.adapters.seam import SeamLocomoAdapter

    adapter = SeamLocomoAdapter()
    adapter._scope_anchor_by_id["scope-a"] = datetime(2024, 1, 1)

    assert adapter._build_temporal_reference(
        "scope-a",
        "what happened three weeks ago?",
    ) == datetime(2023, 12, 11)


def _event(record_id: str, text: str, t0: str) -> MIRLRecord:
    return MIRLRecord(
        id=record_id,
        kind=RecordKind.EVT,
        attrs={"summary": text},
        scope="thread",
        status=Status.ASSERTED,
        conf=1.0,
        t0=t0,
        t1=t0,
    )

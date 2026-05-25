"""H2 substrate: retrieval_event append-only store contract.

The retrieval_event table is the canonical source of retrieval-outcome
training data for the H2 Track-M feedback loop. These tests enforce the
contract documented in docs/roadmap/CONTEXT_STREAMS.md section 12.5:
required fields, append-only semantics, stale-source flagging, and the
read filters consumers will use.
"""

from __future__ import annotations

import pytest

from seam_runtime.storage import SQLiteStore


def _write_basic(store: SQLiteStore, **overrides) -> int:
    defaults = dict(
        run_id="run-fixture",
        query="who attended the wedding?",
        candidate_ids=["raw:turn:101", "raw:turn:102"],
        source_kind="live",
    )
    defaults.update(overrides)
    return store.write_retrieval_event(**defaults)


def test_table_and_indexes_present(tmp_path):
    store = SQLiteStore(tmp_path / "h2.db")
    with store._connect() as conn:
        names = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
        assert "retrieval_event" in names
        idx = {row[0] for row in conn.execute("select name from sqlite_master where type='index'")}
        assert "idx_retrieval_event_run" in idx
        assert "idx_retrieval_event_ts" in idx
        assert "idx_retrieval_event_stale" in idx


def test_write_minimal_returns_event_id_and_round_trips(tmp_path):
    store = SQLiteStore(tmp_path / "h2.db")
    first_id = _write_basic(store)
    second_id = _write_basic(store)
    assert second_id > first_id

    events = store.iter_retrieval_events(run_id="run-fixture")
    assert len(events) == 2
    latest = events[0]
    assert latest["event_id"] == second_id
    assert latest["query"] == "who attended the wedding?"
    assert latest["candidate_ids"] == ["raw:turn:101", "raw:turn:102"]
    assert latest["source_kind"] == "live"
    assert latest["stale_source"] is False
    assert latest["schema_version"] == 1
    assert latest["ranks"] is None
    assert latest["scores"] is None
    assert latest["context_recall"] is None


def test_write_full_optional_fields_round_trip(tmp_path):
    store = SQLiteStore(tmp_path / "h2.db")
    event_id = store.write_retrieval_event(
        run_id="run-full",
        scope="locomo:conv:7",
        query="when did they leave for paris?",
        candidate_ids=["raw:a", "raw:b", "raw:c"],
        ranks=[1, 2, 3],
        scores=[0.91, 0.42, 0.05],
        reasons=["bm25+vector", "vector", "graph"],
        context_hash="ctx-sha256-deadbeef",
        gold_answer="march 14",
        gold_hit_ids=["raw:a"],
        context_recall=1.0,
        judge_score=0.5,
        answer="march 14",
        source_kind="live",
        source_ref="bench:loc-0001",
        extra={"top_score": 0.91, "abstained_by_threshold": False},
    )
    assert event_id >= 1
    [event] = store.iter_retrieval_events(run_id="run-full")
    assert event["scope"] == "locomo:conv:7"
    assert event["ranks"] == [1, 2, 3]
    assert event["scores"] == [0.91, 0.42, 0.05]
    assert event["reasons"] == ["bm25+vector", "vector", "graph"]
    assert event["context_hash"] == "ctx-sha256-deadbeef"
    assert event["gold_answer"] == "march 14"
    assert event["gold_hit_ids"] == ["raw:a"]
    assert event["context_recall"] == 1.0
    assert event["judge_score"] == 0.5
    assert event["answer"] == "march 14"
    assert event["source_ref"] == "bench:loc-0001"
    assert event["extra"] == {"top_score": 0.91, "abstained_by_threshold": False}


def test_stale_source_flag_round_trips_and_filters(tmp_path):
    store = SQLiteStore(tmp_path / "h2.db")
    _write_basic(store, run_id="run-stale", source_kind="backfill", source_ref="bil2:pre-240", stale_source=True)
    _write_basic(store, run_id="run-stale", source_kind="live")

    all_events = store.iter_retrieval_events(run_id="run-stale", include_stale=True)
    fresh_only = store.iter_retrieval_events(run_id="run-stale", include_stale=False)
    assert len(all_events) == 2
    assert len(fresh_only) == 1
    assert fresh_only[0]["stale_source"] is False
    assert store.count_retrieval_events(run_id="run-stale") == 2
    assert store.count_retrieval_events(run_id="run-stale", include_stale=False) == 1


def test_iter_filters_by_run_and_scope_and_limit(tmp_path):
    store = SQLiteStore(tmp_path / "h2.db")
    _write_basic(store, run_id="run-a", scope="conv:1")
    _write_basic(store, run_id="run-a", scope="conv:2")
    _write_basic(store, run_id="run-b", scope="conv:1")

    assert len(store.iter_retrieval_events(run_id="run-a")) == 2
    assert len(store.iter_retrieval_events(scope="conv:1")) == 2
    assert len(store.iter_retrieval_events(run_id="run-a", scope="conv:1")) == 1
    assert len(store.iter_retrieval_events(limit=2)) == 2


def test_append_only_contract_no_mutation_api(tmp_path):
    """H2 guardrail: no update/delete API. Mutating events would break the
    training-data audit trail."""
    store = SQLiteStore(tmp_path / "h2.db")
    forbidden = ("update_retrieval_event", "delete_retrieval_event", "purge_retrieval_events", "edit_retrieval_event")
    for name in forbidden:
        assert not hasattr(store, name), f"SQLiteStore should not expose {name}"


def test_validation_rejects_missing_required(tmp_path):
    store = SQLiteStore(tmp_path / "h2.db")
    with pytest.raises(ValueError):
        store.write_retrieval_event(run_id="", query="q", candidate_ids=[], source_kind="live")
    with pytest.raises(ValueError):
        store.write_retrieval_event(run_id="r", query="", candidate_ids=[], source_kind="live")
    with pytest.raises(ValueError):
        store.write_retrieval_event(run_id="r", query="q", candidate_ids=[], source_kind="")


def test_validation_rejects_misaligned_ranks_and_scores(tmp_path):
    store = SQLiteStore(tmp_path / "h2.db")
    with pytest.raises(ValueError):
        store.write_retrieval_event(
            run_id="r", query="q", candidate_ids=["a", "b"], source_kind="live", ranks=[1]
        )
    with pytest.raises(ValueError):
        store.write_retrieval_event(
            run_id="r", query="q", candidate_ids=["a", "b"], source_kind="live", scores=[0.1]
        )


def test_empty_candidate_ids_allowed(tmp_path):
    """An empty candidate set is a valid retrieval outcome (the query
    matched nothing). Recording it is more useful than dropping it."""
    store = SQLiteStore(tmp_path / "h2.db")
    event_id = store.write_retrieval_event(
        run_id="run-empty",
        query="something nobody asked about",
        candidate_ids=[],
        source_kind="live",
    )
    [event] = store.iter_retrieval_events(run_id="run-empty")
    assert event["event_id"] == event_id
    assert event["candidate_ids"] == []

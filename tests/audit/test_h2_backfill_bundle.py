"""H2 slice 3: backfill retrieval_event rows from existing result bundles.

Pins the join contract (bundle case -> source dataset by case_id), the
stale-by-default flag, the populated/null field shape for the partial
data that bundles preserve, and the CLI's multi-bundle aggregation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.external.common.dataset import load_quickstart_cases
from seam_runtime.storage import SQLiteStore
from tools.h2 import backfill_bundle as bb


def _quickstart_case_ids() -> list[str]:
    return [c.case_id for c in load_quickstart_cases()]


def _make_bundle(
    tmp_path: Path,
    *,
    case_ids: list[str],
    name: str = "bundle.json",
    adapter: str = "seam",
    run_started_at: str = "2026-05-01T00:00:00+00:00",
    save_context: bool = True,
    include_judge: bool = True,
) -> Path:
    """Synthesize a minimal LoCoMo result bundle that exercises every
    backfill code path (recall, judge, save_context, latencies, answerer
    diagnostics)."""
    cases = []
    for i, cid in enumerate(case_ids):
        entry: dict = {
            "case_id": cid,
            "category": "fact",
            "scores": {
                "context_recall": 0.5 + i * 0.1,
                "answer_em": 0.0,
                "answer_f1": 0.25,
            },
            "retrieval_latency_ms": 12.5 + i,
            "answer_latency_ms": 30.0 + i,
        }
        if save_context:
            entry["retrieved_context"] = f"context for {cid} :: turn snippet"
            entry["answerer_diagnostics"] = {
                "provider": "openai",
                "finish_reason": "stop",
                "content_len": 6,
                "content_preview": f"ans{i}",
            }
        if include_judge:
            entry["judge"] = {
                "verdict": "correct" if i == 0 else "wrong",
                "score": 1.0 if i == 0 else 0.0,
                "rationale": "n/a",
                "judge_name": "stub",
                "judge_model": "stub-v0",
            }
        cases.append(entry)

    bundle = {
        "version": "1.0",
        "benchmark": "locomo",
        "adapter": adapter,
        "dataset": {"source": "quickstart", "case_count": len(cases)},
        "run_started_at": run_started_at,
        "elapsed_seconds": 1.0,
        "scores": {"context_recall_mean": 0.5},
        "cases": cases,
        "integrity_hash": "0" * 64,
    }
    path = tmp_path / name
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return path


def test_quickstart_source_resolves_to_bundled_fixture():
    cases = bb.load_source_cases("quickstart")
    assert len(cases) >= 1
    assert all(case.question for case in cases)
    assert all(case.gold_answer for case in cases)


def test_unknown_source_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        bb.load_source_cases(tmp_path / "nope.json")


def test_scope_derivation_strips_question_suffix():
    assert bb._scope_from_case_id("conv-1::q0") == "locomo:conv-1"
    assert bb._scope_from_case_id("sample_42::q7") == "locomo:sample_42"
    # Malformed -> None so the writer falls back to the adapter-level scope.
    assert bb._scope_from_case_id("malformed") is None


def test_derive_run_id_prefers_timestamp_over_filename(tmp_path):
    bundle = {"adapter": "seam", "run_started_at": "2026-05-26T12:34:56+00:00"}
    rid = bb.derive_run_id(bundle, tmp_path / "ignored.json")
    assert rid.startswith("backfill-seam-2026")
    # No timestamp -> falls back to filename stem.
    rid2 = bb.derive_run_id({"adapter": "mem0"}, tmp_path / "fixture-name.json")
    assert rid2 == "backfill-mem0-fixture-name"


def test_round_trip_quickstart_bundle_writes_one_event_per_case(tmp_path):
    case_ids = _quickstart_case_ids()
    bundle_path = _make_bundle(tmp_path, case_ids=case_ids)
    db = SQLiteStore(tmp_path / "h2.db")

    summary = bb.backfill_bundle(
        bundle_path=bundle_path,
        source="quickstart",
        store=db,
        stale=True,
    )

    assert summary.events_written == len(case_ids)
    assert summary.cases_in_bundle == len(case_ids)
    assert summary.cases_skipped_no_match == 0
    assert summary.cases_skipped_invalid == 0
    assert db.count_retrieval_events(run_id=summary.run_id) == len(case_ids)


def test_event_populates_join_and_partial_fields(tmp_path):
    case_ids = _quickstart_case_ids()
    bundle_path = _make_bundle(tmp_path, case_ids=case_ids[:1])
    db = SQLiteStore(tmp_path / "h2.db")
    summary = bb.backfill_bundle(
        bundle_path=bundle_path, source="quickstart", store=db, stale=True
    )

    [event] = db.iter_retrieval_events(run_id=summary.run_id)
    source_case = next(c for c in load_quickstart_cases() if c.case_id == case_ids[0])

    # Joined from the source dataset.
    assert event["query"] == source_case.question
    assert event["gold_answer"] == source_case.gold_answer
    # Scope parsed from case_id.
    assert event["scope"] == f"locomo:{case_ids[0].split('::')[0]}"
    # Bundles do not carry candidate metadata.
    assert event["candidate_ids"] == []
    assert event["ranks"] is None
    assert event["scores"] is None
    # Recall + judge + answer preview pulled from the bundle.
    assert event["context_recall"] == 0.5
    assert event["judge_score"] == 1.0
    assert event["answer"] == "ans0"
    # save_context produced a retrieved_context, so the hash is set.
    ctx_hash = hashlib.sha256(
        f"context for {case_ids[0]} :: turn snippet".encode("utf-8")
    ).hexdigest()
    assert event["context_hash"] == ctx_hash
    # Stale + backfill provenance.
    assert event["stale_source"] is True
    assert event["source_kind"] == "backfill"
    assert event["source_ref"].startswith("bundle:")
    assert event["source_ref"].endswith(f"::{case_ids[0]}")
    # Extras carry the rest of the bundle context for slice 4/5 use.
    extra = event["extra"]
    assert extra["category"] == "fact"
    assert extra["retrieval_latency_ms"] == 12.5
    assert extra["scores"]["answer_f1"] == 0.25
    assert extra["judge"]["verdict"] == "correct"


def test_bundle_without_save_context_leaves_hash_and_answer_null(tmp_path):
    case_ids = _quickstart_case_ids()[:1]
    bundle_path = _make_bundle(
        tmp_path, case_ids=case_ids, save_context=False, include_judge=False
    )
    db = SQLiteStore(tmp_path / "h2.db")
    summary = bb.backfill_bundle(
        bundle_path=bundle_path, source="quickstart", store=db, stale=True
    )
    [event] = db.iter_retrieval_events(run_id=summary.run_id)
    assert event["context_hash"] is None
    assert event["answer"] is None
    assert event["judge_score"] is None
    # Recall is still present (it's in scores even without save_context).
    assert event["context_recall"] == 0.5


def test_cases_not_in_source_dataset_are_skipped(tmp_path):
    bundle_path = _make_bundle(
        tmp_path,
        case_ids=[_quickstart_case_ids()[0], "nonexistent::q99"],
    )
    db = SQLiteStore(tmp_path / "h2.db")
    summary = bb.backfill_bundle(
        bundle_path=bundle_path, source="quickstart", store=db, stale=True
    )
    assert summary.events_written == 1
    assert summary.cases_skipped_no_match == 1


def test_no_stale_flag_writes_fresh_rows(tmp_path):
    case_ids = _quickstart_case_ids()[:1]
    bundle_path = _make_bundle(tmp_path, case_ids=case_ids)
    db = SQLiteStore(tmp_path / "h2.db")
    summary = bb.backfill_bundle(
        bundle_path=bundle_path, source="quickstart", store=db, stale=False
    )
    [event] = db.iter_retrieval_events(run_id=summary.run_id)
    assert event["stale_source"] is False
    # Filtering with include_stale=False must now find the row.
    assert db.count_retrieval_events(include_stale=False) == 1


def test_run_id_override_groups_all_events(tmp_path):
    case_ids = _quickstart_case_ids()
    b1 = _make_bundle(tmp_path, case_ids=case_ids[:1], name="b1.json", run_started_at="2026-05-01T00:00:00Z")
    b2 = _make_bundle(tmp_path, case_ids=case_ids[1:], name="b2.json", run_started_at="2026-05-02T00:00:00Z")
    db = SQLiteStore(tmp_path / "h2.db")
    bb.backfill_bundle(bundle_path=b1, source="quickstart", store=db, run_id="manual-run", stale=True)
    bb.backfill_bundle(bundle_path=b2, source="quickstart", store=db, run_id="manual-run", stale=True)
    assert db.count_retrieval_events(run_id="manual-run") == len(case_ids)


def test_cli_main_writes_events_and_prints_summary(tmp_path, capsys):
    case_ids = _quickstart_case_ids()
    b1 = _make_bundle(tmp_path, case_ids=case_ids[:1], name="b1.json")
    b2 = _make_bundle(tmp_path, case_ids=case_ids[1:2], name="b2.json")
    db_path = tmp_path / "cli.db"

    rc = bb.main(
        [
            "--bundle", str(b1),
            "--bundle", str(b2),
            "--source", "quickstart",
            "--db", str(db_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "b1.json" in out
    assert "b2.json" in out
    assert "total events written: 2" in out
    db = SQLiteStore(db_path)
    assert db.count_retrieval_events() == 2

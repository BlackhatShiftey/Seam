"""H2 self-improvement loop, back half: the ``apply`` step.

Pins the contract that turns an approved improvement proposal into an active
retrieval-flag change:

* the locked-baseline invariant (empty flag-state + empty env reproduces
  ``RetrievalFlags()`` byte-identical),
* apply materializes only approved, non-holdout-violating proposals that carry
  a recognized ``{"flags": {...}}`` payload,
* apply is a *reconcile* (pure projection of the approved set), so withdrawing
  an approval and re-running removes the flag instead of ratcheting it on,
* newest approved proposal wins a per-flag conflict,
* payload gating is on shape, not ``kind``; unknown/ill-typed flags are skipped
  without crashing the scoring path,
* the env layer overrides persisted applied-state (operator kill switch).
"""

from __future__ import annotations

from pathlib import Path

from seam_runtime.retrieval import RetrievalFlags, load_retrieval_flags
from seam_runtime.storage import SQLiteStore
from tools.h2 import improvement_review as ir


def _store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "h2apply.db")


def _propose(store: SQLiteStore, change: dict | None, *, kind: str = "ranking_weight") -> int:
    return store.write_improvement_proposal(
        kind=kind,
        summary="test proposal",
        proposed_change=change,
    )


def _approve(store: SQLiteStore, pid: int) -> None:
    store.record_proposal_decision(proposal_id=pid, status="approved")


def _apply(store: SQLiteStore, *, dry_run: bool = False):
    desired, applied, skipped = ir.compute_apply_plan(store)
    if not dry_run:
        store.replace_retrieval_flag_state(desired)
    return desired, applied, skipped


# ---- baseline invariant ------------------------------------------------------


def test_empty_state_reproduces_baseline(tmp_path):
    store = _store(tmp_path)
    # No applied state, no env -> byte-identical to the locked defaults.
    assert load_retrieval_flags(store, env={}) == RetrievalFlags()


def test_table_present(tmp_path):
    store = _store(tmp_path)
    with store._connect() as conn:
        tables = {row[0] for row in conn.execute("select name from sqlite_master where type='table'")}
    assert "retrieval_flag_state" in tables


# ---- happy path: approved + flags payload applies ----------------------------


def test_approved_flag_payload_applies(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"flags": {"bm25_all_kinds": True}})
    _approve(store, pid)

    _, applied, skipped = _apply(store)

    assert applied == [{"flag": "bm25_all_kinds", "value": True, "proposal_id": pid}]
    assert skipped == []
    assert load_retrieval_flags(store, env={}).bm25_all_kinds is True


def test_fusion_and_rrf_k_apply(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"flags": {"fusion": "rrf", "rrf_k": 30}})
    _approve(store, pid)
    _apply(store)

    flags = load_retrieval_flags(store, env={})
    assert flags.fusion == "rrf"
    assert flags.rrf_k == 30


# ---- gating: only approved + non-violating + valid payload -------------------


def test_pending_proposal_is_not_applied(tmp_path):
    store = _store(tmp_path)
    _propose(store, {"flags": {"bm25_all_kinds": True}})  # left pending

    desired, applied, _ = _apply(store)

    assert desired == {}
    assert applied == []
    assert load_retrieval_flags(store, env={}) == RetrievalFlags()


def test_rejected_proposal_is_not_applied(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"flags": {"bm25_all_kinds": True}})
    store.record_proposal_decision(proposal_id=pid, status="rejected")

    _, applied, skipped = _apply(store)

    assert applied == []
    assert {s["proposal_id"] for s in skipped} == {pid}
    assert load_retrieval_flags(store, env={}).bm25_all_kinds is False


def test_holdout_violation_is_not_applied(tmp_path):
    store = _store(tmp_path)
    pid = store.write_improvement_proposal(
        kind="ranking_weight",
        summary="violating",
        proposed_change={"flags": {"bm25_all_kinds": True}},
        holdout_violation=True,
    )
    _approve(store, pid)  # approved but holdout-violating -> still blocked

    _, applied, skipped = _apply(store)

    assert applied == []
    assert any(s["proposal_id"] == pid and s.get("holdout_violation") for s in skipped)
    assert load_retrieval_flags(store, env={}).bm25_all_kinds is False


def test_unknown_flag_and_wrong_type_are_skipped(tmp_path):
    store = _store(tmp_path)
    pid = _propose(
        store,
        {"flags": {"not_a_flag": True, "bm25_all_kinds": "yes", "scoped_vectors": True}},
    )
    _approve(store, pid)

    _, applied, skipped = _apply(store)

    # only the well-typed flag survives; the other two are reported skips
    assert applied == [{"flag": "scoped_vectors", "value": True, "proposal_id": pid}]
    reasons = " ".join(s["reason"] for s in skipped)
    assert "not_a_flag" in reasons and "bm25_all_kinds" in reasons
    # the scoring path still loads cleanly with the one valid flag set
    flags = load_retrieval_flags(store, env={})
    assert flags.scoped_vectors is True
    assert flags.bm25_all_kinds is False


def test_invalid_fusion_value_skipped(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"flags": {"fusion": "bogus"}})
    _approve(store, pid)

    _, applied, skipped = _apply(store)

    assert applied == []
    assert any("fusion" in s["reason"] for s in skipped)


def test_approved_without_flags_payload_is_noop(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"note": "protocol change"}, kind="schema_change")
    _approve(store, pid)

    desired, applied, skipped = _apply(store)

    assert desired == {} and applied == [] and skipped == []


# ---- reconcile: reversible, latest-wins, idempotent --------------------------


def test_apply_is_reversible_on_withdrawn_approval(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"flags": {"bm25_all_kinds": True}})
    _approve(store, pid)
    _apply(store)
    assert load_retrieval_flags(store, env={}).bm25_all_kinds is True

    # Withdraw approval; re-apply must REMOVE the flag, not leave it ratcheted on.
    store.record_proposal_decision(proposal_id=pid, status="rejected")
    desired, applied, _ = _apply(store)

    assert desired == {} and applied == []
    assert load_retrieval_flags(store, env={}) == RetrievalFlags()


def test_newest_approved_proposal_wins_conflict(tmp_path):
    store = _store(tmp_path)
    old = _propose(store, {"flags": {"bm25_all_kinds": True}})
    _approve(store, old)
    new = _propose(store, {"flags": {"bm25_all_kinds": False}})
    _approve(store, new)

    desired, _, _ = _apply(store)

    assert desired["bm25_all_kinds"][1] == new  # newest proposal id is the source
    assert load_retrieval_flags(store, env={}).bm25_all_kinds is False


def test_apply_is_idempotent(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"flags": {"bm25_all_kinds": True}})
    _approve(store, pid)

    first = _apply(store)[0]
    second = _apply(store)[0]

    assert first == second
    assert load_retrieval_flags(store, env={}).bm25_all_kinds is True


def test_dry_run_writes_nothing(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"flags": {"bm25_all_kinds": True}})
    _approve(store, pid)

    _, applied, _ = _apply(store, dry_run=True)

    assert applied == [{"flag": "bm25_all_kinds", "value": True, "proposal_id": pid}]
    # nothing persisted -> still baseline
    assert load_retrieval_flags(store, env={}) == RetrievalFlags()


# ---- env layer wins over persisted applied-state -----------------------------


def test_env_overrides_persisted_state(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"flags": {"bm25_all_kinds": True}})
    _approve(store, pid)
    _apply(store)

    # Applied state says True; an explicit env override of 0 must win.
    flags = load_retrieval_flags(store, env={"SEAM_RETRIEVAL_BM25_ALL": "0"})
    assert flags.bm25_all_kinds is False


def test_unset_env_does_not_clobber_persisted_state(tmp_path):
    store = _store(tmp_path)
    pid = _propose(store, {"flags": {"bm25_all_kinds": True}})
    _approve(store, pid)
    _apply(store)

    # An unrelated env var set; the applied flag must survive (not reset to default).
    flags = load_retrieval_flags(store, env={"SEAM_RETRIEVAL_RRF": "1"})
    assert flags.bm25_all_kinds is True
    assert flags.fusion == "rrf"


# ---- CLI smoke ---------------------------------------------------------------


def test_cli_apply_smoke(tmp_path):
    db = tmp_path / "cli.db"
    store = SQLiteStore(db)
    pid = _propose(store, {"flags": {"scoped_vectors": True}})
    _approve(store, pid)

    rc = ir.main(["apply", "--db", str(db), "--json"])

    assert rc == 0
    assert load_retrieval_flags(SQLiteStore(db), env={}).scoped_vectors is True

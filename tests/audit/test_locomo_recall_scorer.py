"""Free LoCoMo recall scorer: mechanism + flag-override safety.

CI-safe: builds a tiny synthetic conversation through the real adapter (no
external LoCoMo dataset, no answerer/judge, no paid call). The dataset-driven
path (`build_locomo_recall_scorers`) and the headroom it exposes are validated
manually against the real corpus; here we pin the scorer contract.
"""

from __future__ import annotations

from collections import OrderedDict

from benchmarks.external.common.types import BenchmarkCase, ConversationTurn
from benchmarks.external.locomo.adapters.seam import SeamLocomoAdapter
from benchmarks.external.locomo.recall_scorer import (
    LocomoRecallScorer,
    PooledLocomoRecallScorer,
    _select_split,
    scope_for,
)
from seam_runtime.retrieval import RetrievalFlags
from tools.h2.holdout_split import DEFAULT_RATIO, DEFAULT_SALT, assign_one


def test_scope_for_strips_question_suffix():
    assert scope_for("conv-26::q0") == "conv-26"
    assert scope_for("conv-26") == "conv-26"


def _ingest(adapter: SeamLocomoAdapter, scope: str, turns):
    adapter.reset(scope)
    for turn in turns:
        adapter.ingest_turn(scope, turn)


def test_locomo_recall_scorer_mechanism_and_flag_restore(tmp_path):
    turns = (
        ConversationTurn(speaker="Ana", text="The project deadline is Friday, March 7."),
        ConversationTurn(speaker="Ben", text="We store everything in Postgres."),
        ConversationTurn(speaker="Ana", text="The standup moved to 9:30 am."),
    )
    adapter = SeamLocomoAdapter(db_path=str(tmp_path / "loc"), keep_db=True, answerer=None)
    scope = "conv-x"
    _ingest(adapter, scope, turns)
    cases = [
        BenchmarkCase(
            case_id="conv-x::q0", conversation=turns,
            question="When is the project deadline?", gold_answer="Friday", category="1",
        ),
        BenchmarkCase(
            case_id="conv-x::q1", conversation=turns,
            question="What database do they use?", gold_answer="Postgres", category="2",
        ),
    ]
    scorer = LocomoRecallScorer(adapter=adapter, scope=scope, cases=cases)
    rt = adapter._runtime(scope)
    assert rt._retrieval_flags is None  # not yet resolved

    report = scorer.score(None, flags=RetrievalFlags())

    assert report.scorer == "locomo_recall"
    assert report.n == 2
    assert 0.0 <= report.aggregate <= 1.0
    assert set(report.per_case) == {"conv-x::q0", "conv-x::q1"}
    assert set(report.per_category) == {"1", "2"}
    # the override is restored after scoring (was None before)
    assert rt._retrieval_flags is None


def test_locomo_recall_scorer_runs_under_candidate_flags(tmp_path):
    turns = (
        ConversationTurn(speaker="Ana", text="My flight to Lisbon leaves at 6:45 am."),
        ConversationTurn(speaker="Ben", text="Bring the blue folder to the review."),
    )
    adapter = SeamLocomoAdapter(db_path=str(tmp_path / "loc2"), keep_db=True, answerer=None)
    scope = "conv-y"
    _ingest(adapter, scope, turns)
    cases = [BenchmarkCase(
        case_id="conv-y::q0", conversation=turns,
        question="Where is the flight going?", gold_answer="Lisbon", category="1",
    )]
    scorer = LocomoRecallScorer(adapter=adapter, scope=scope, cases=cases)

    # both baseline and an explicit candidate run cleanly and are well-formed
    base = scorer.score(None, flags=RetrievalFlags())
    cand = scorer.score(None, flags=RetrievalFlags(semantic_zero_no_vector=True, w_semantic=0.45))

    assert base.n == cand.n == 1
    assert 0.0 <= base.aggregate <= 1.0 and 0.0 <= cand.aggregate <= 1.0


def _case(cid, category="1"):
    return BenchmarkCase(case_id=cid, conversation=(), question="q?", gold_answer="a", category=category)


def test_select_split_partitions_deterministically():
    cases = [_case(f"conv-{i}::q{j}") for i in range(4) for j in range(6)]
    dev = _select_split(cases, "dev", salt=DEFAULT_SALT, ratio=DEFAULT_RATIO)
    hold = _select_split(cases, "holdout", salt=DEFAULT_SALT, ratio=DEFAULT_RATIO)
    dev_ids = {c.case_id for c in dev}
    hold_ids = {c.case_id for c in hold}
    # dev and holdout are disjoint and cover everything; matches assign_one
    assert dev_ids.isdisjoint(hold_ids)
    assert dev_ids | hold_ids == {c.case_id for c in cases}
    for c in cases:
        want = assign_one(c.case_id, salt=DEFAULT_SALT, ratio=DEFAULT_RATIO)
        assert (c in dev) == (want == "dev")
    # split=None keeps everything
    assert len(_select_split(cases, None, salt=DEFAULT_SALT, ratio=DEFAULT_RATIO)) == len(cases)


def test_pooled_scorer_spans_multiple_conversations(tmp_path):
    adapter = SeamLocomoAdapter(db_path=str(tmp_path / "pool"), keep_db=True, answerer=None)
    convs = {
        "conv-a": (ConversationTurn(speaker="Ana", text="The deadline is Friday March 7."),),
        "conv-b": (ConversationTurn(speaker="Ben", text="We store data in Postgres 16."),),
    }
    cases_by_scope = OrderedDict()
    for scope, turns in convs.items():
        _ingest(adapter, scope, turns)
        cases_by_scope[scope] = [
            BenchmarkCase(case_id=f"{scope}::q0", conversation=turns,
                          question="when/what?", gold_answer="Friday" if scope == "conv-a" else "Postgres",
                          category="1" if scope == "conv-a" else "2")
        ]
    scorer = PooledLocomoRecallScorer(adapter=adapter, cases_by_scope=cases_by_scope)
    rt_a, rt_b = adapter._runtime("conv-a"), adapter._runtime("conv-b")

    report = scorer.score(None, flags=RetrievalFlags())

    assert report.n == 2                                   # pooled across both conversations
    assert set(report.per_case) == {"conv-a::q0", "conv-b::q0"}
    assert set(report.per_category) == {"1", "2"}
    # flag override restored on every touched runtime
    assert rt_a._retrieval_flags is None and rt_b._retrieval_flags is None

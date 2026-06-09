"""Free LoCoMo recall scorer: mechanism + flag-override safety.

CI-safe: builds a tiny synthetic conversation through the real adapter (no
external LoCoMo dataset, no answerer/judge, no paid call). The dataset-driven
path (`build_locomo_recall_scorers`) and the headroom it exposes are validated
manually against the real corpus; here we pin the scorer contract.
"""

from __future__ import annotations

from benchmarks.external.common.types import BenchmarkCase, ConversationTurn
from benchmarks.external.locomo.adapters.seam import SeamLocomoAdapter
from benchmarks.external.locomo.recall_scorer import LocomoRecallScorer, scope_for
from seam_runtime.retrieval import RetrievalFlags


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

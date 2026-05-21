"""Tests for abstain threshold in the LoCoMo adapter."""

from benchmarks.external.common.types import ConversationTurn
from benchmarks.external.locomo.adapters.seam import SeamLocomoAdapter


def test_abstain_threshold_zero_unchanged(tmp_path):
    """Default abstain_threshold 0.0 keeps existing behavior."""
    adapter = SeamLocomoAdapter(db_path=str(tmp_path), budget=2000)
    assert adapter._abstain_threshold == 0.0

    scope_id = "abstain-zero"
    adapter.reset(scope_id)
    adapter.ingest_turn(
        scope_id,
        ConversationTurn(
            speaker="Alice", text="My favorite color is blue.",
            timestamp="2024-01-01T00:00:00Z",
        ),
    )
    answer = adapter.answer(scope_id, "What is Alice's favorite color?")
    assert answer.generated_answer is None  # no answerer configured


def test_abstain_threshold_one_emits_unknown(tmp_path, monkeypatch):
    """With threshold 1.0, every answer becomes 'unknown' when an answerer is set."""
    monkeypatch.setattr(
        "benchmarks.external.locomo.adapters.seam._openai_short_answer",
        lambda model, prompt, max_tokens=64: "blue",
    )
    adapter = SeamLocomoAdapter(
        db_path=str(tmp_path), budget=2000,
        answerer="openai", answerer_model="gpt-4o-mini",
        abstain_threshold=1.0,
    )

    scope_id = "abstain-one"
    adapter.reset(scope_id)
    adapter.ingest_turn(
        scope_id,
        ConversationTurn(
            speaker="Alice", text="My favorite color is blue.",
            timestamp="2024-01-01T00:00:00Z",
        ),
    )
    answer = adapter.answer(scope_id, "What is Alice's favorite color?")
    assert answer.generated_answer == "unknown", (
        f"Expected 'unknown' with threshold 1.0, got {answer.generated_answer!r}"
    )


def test_abstain_verdict_in_aggregate():
    """aggregate_judge_scores counts abstain verdicts."""
    from benchmarks.external.common.scoring import aggregate_judge_scores

    verdicts = [
        {"verdict": "correct", "score": 1.0},
        {"verdict": "abstain", "score": 0.0},
        {"verdict": "correct", "score": 1.0},
    ]
    result = aggregate_judge_scores(verdicts)
    assert result["correct_count"] == 2
    assert result["abstain_count"] == 1
    assert result["incorrect_count"] == 0

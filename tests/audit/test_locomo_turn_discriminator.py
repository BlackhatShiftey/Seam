"""Regression gate: per-turn source_ref discriminator prevents ID collisions."""

from benchmarks.external.common.types import ConversationTurn
from benchmarks.external.locomo.adapters.seam import SeamLocomoAdapter


def test_two_turns_both_retrievable(tmp_path):
    """Two distinct turns must both store RAW content retrievable independently."""
    adapter = SeamLocomoAdapter(db_path=str(tmp_path), budget=2000)
    scope_id = "discriminator-test"

    adapter.reset(scope_id)
    adapter.ingest_turn(
        scope_id,
        ConversationTurn(
            speaker="Alice",
            text="I adopted a cat named Pixel in Tokyo.",
            timestamp="2024-01-15T10:00:00Z",
        ),
    )
    adapter.ingest_turn(
        scope_id,
        ConversationTurn(
            speaker="Bob",
            text="I bought a dog named Rusty in Osaka.",
            timestamp="2024-01-16T10:00:00Z",
        ),
    )

    answer_alice = adapter.answer(scope_id, "What is the name of Alice's pet?")
    answer_bob = adapter.answer(scope_id, "What is the name of Bob's pet?")

    assert "Pixel" in answer_alice.retrieved_context, (
        f"Alice's turn content should be retrievable; got: {answer_alice.retrieved_context[:200]}"
    )
    assert "Rusty" in answer_bob.retrieved_context, (
        f"Bob's turn content should be retrievable; got: {answer_bob.retrieved_context[:200]}"
    )

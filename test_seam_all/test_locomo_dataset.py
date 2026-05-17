from __future__ import annotations

from benchmarks.external.common.dataset import (
    QUICKSTART_FIXTURE_PATH,
    load_locomo_cases,
    load_quickstart_cases,
)


def test_load_quickstart_fixture() -> None:
    """Loading the quickstart fixture yields at least 5 cases, each well-formed."""
    cases = load_locomo_cases(QUICKSTART_FIXTURE_PATH)
    assert len(cases) >= 5, f"expected >= 5 cases, got {len(cases)}"

    for case in cases:
        assert case.question, f"case {case.case_id!r} has empty question"
        assert case.gold_answer, f"case {case.case_id!r} has empty gold_answer"
        assert case.conversation, f"case {case.case_id!r} has empty conversation"
        assert "::q" in case.case_id, (
            f"case_id {case.case_id!r} missing '::q' segment"
        )


def test_quickstart_cases_have_unique_ids() -> None:
    """Every case loaded from the quickstart fixture has a unique case_id."""
    cases = load_locomo_cases(QUICKSTART_FIXTURE_PATH)
    ids = [case.case_id for case in cases]
    assert len(ids) == len(set(ids)), (
        f"duplicate case_ids detected: {len(ids)} total, {len(set(ids))} unique"
    )


def test_quickstart_conversation_turns_have_speakers() -> None:
    """Each turn in every conversation has a non-empty speaker and text."""
    cases = load_locomo_cases(QUICKSTART_FIXTURE_PATH)
    for case in cases:
        for i, turn in enumerate(case.conversation):
            assert turn.speaker, (
                f"case {case.case_id!r} turn {i} has empty speaker"
            )
            assert turn.text, (
                f"case {case.case_id!r} turn {i} has empty text"
            )


def test_load_quickstart_cases_helper() -> None:
    """load_quickstart_cases() returns the same result as load_locomo_cases(fixture_path)."""
    direct = load_locomo_cases(QUICKSTART_FIXTURE_PATH)
    helper = load_quickstart_cases()
    assert len(direct) == len(helper), (
        f"count mismatch: direct={len(direct)}, helper={len(helper)}"
    )
    for a, b in zip(direct, helper):
        assert a.case_id == b.case_id, (
            f"case_id mismatch: {a.case_id!r} != {b.case_id!r}"
        )
        assert a.question == b.question
        assert a.gold_answer == b.gold_answer
        assert len(a.conversation) == len(b.conversation)
        for i, (ta, tb) in enumerate(zip(a.conversation, b.conversation)):
            assert ta.speaker == tb.speaker
            assert ta.text == tb.text

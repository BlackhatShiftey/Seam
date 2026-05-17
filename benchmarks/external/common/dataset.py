from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmarks.external.common.types import BenchmarkCase, ConversationTurn

QUICKSTART_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "locomo" / "fixtures" / "quickstart.json"
)


def load_locomo_cases(path: str | Path) -> list[BenchmarkCase]:
    """Parse a LoCoMo JSON file into BenchmarkCase records.

    One case per Q/A pair.  case_id = f"{sample_id}::q{qa_index}".
    The full conversation (all sessions / dialogs flattened) is shared across
    every qa pair belonging to the same sample.
    """
    path = Path(path)

    with path.open("r", encoding="utf-8") as fh:
        raw: list[dict[str, Any]] = json.load(fh)

    cases: list[BenchmarkCase] = []

    for sample in raw:
        sample_id: str = sample["sample_id"]

        # --- flatten conversation into a single ordered tuple of turns ---
        conversation: list[ConversationTurn] = []
        conversation_data = sample["conversation"]
        sessions: list[dict[str, Any]] = conversation_data["sessions"]

        for session in sessions:
            timestamp: str | None = session.get("date_time") or None
            for dialog in session.get("dialogs", []):
                speaker = dialog["speaker"]
                text = dialog["text"]
                conversation.append(
                    ConversationTurn(speaker=speaker, text=text, timestamp=timestamp)
                )

        conversation_tuple: tuple[ConversationTurn, ...] = tuple(conversation)

        # --- one BenchmarkCase per QA pair ---
        qa_list: list[dict[str, Any]] = sample.get("qa", [])
        for qa_index, qa in enumerate(qa_list):
            case_id = f"{sample_id}::q{qa_index}"
            question = qa["question"]
            gold_answer = qa["answer"]
            # category may be absent, an int, or a str
            raw_category = qa.get("category")
            category: str | None = (
                str(raw_category) if raw_category is not None else None
            )

            cases.append(
                BenchmarkCase(
                    case_id=case_id,
                    conversation=conversation_tuple,
                    question=question,
                    gold_answer=gold_answer,
                    category=category,
                )
            )

    return cases


def load_quickstart_cases() -> list[BenchmarkCase]:
    """Load the bundled quickstart fixture."""
    return load_locomo_cases(QUICKSTART_FIXTURE_PATH)

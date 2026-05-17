from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConversationTurn:
    speaker: str
    text: str
    timestamp: str | None = None  # ISO 8601 when present


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    conversation: tuple[ConversationTurn, ...]
    question: str
    gold_answer: str
    category: str | None = None  # LoCoMo question category if present


@dataclass(frozen=True)
class AdapterAnswer:
    retrieved_context: str           # joined retrieved text (always populated)
    generated_answer: str | None = None  # only if the adapter generates an answer
    retrieval_latency_ms: float = 0.0
    answer_latency_ms: float = 0.0


class MemorySystemAdapter(Protocol):
    name: str

    def reset(self, scope_id: str) -> None: ...
    def ingest_turn(self, scope_id: str, turn: ConversationTurn) -> None: ...
    def answer(self, scope_id: str, question: str) -> AdapterAnswer: ...

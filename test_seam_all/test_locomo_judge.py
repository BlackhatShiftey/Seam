from __future__ import annotations

import json
import subprocess
import sys

import pytest

from benchmarks.external.common.judge import (
    ClaudeJudge,
    JudgeVerdict,
    OpenAIJudge,
    StubJudge,
    build_judge,
)
from benchmarks.external.common.runner import run_benchmark
from benchmarks.external.common.types import (
    AdapterAnswer,
    BenchmarkCase,
    ConversationTurn,
    MemorySystemAdapter,
)


class _MinimalAdapter:
    """In-memory adapter for testing judge integration without SEAM runtime."""
    name = "minimal"
    _store: dict[str, str]

    def __init__(self):
        self._store = {}

    def reset(self, scope_id: str) -> None:
        self._store.pop(scope_id, None)

    def ingest_turn(self, scope_id: str, turn: ConversationTurn) -> None:
        self._store[scope_id] = turn.text

    def answer(self, scope_id: str, question: str) -> AdapterAnswer:
        ctx = self._store.get(scope_id, "")
        return AdapterAnswer(retrieved_context=ctx)


class _ErrorJudge:
    """Judge that always raises — tests error handling."""
    name = "error"
    model = "error-1"

    def score(self, *, question, gold, pred) -> JudgeVerdict:
        raise RuntimeError("simulated judge failure")


def _minimal_cases(n: int = 2) -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            case_id=f"test-{i}",
            conversation=(ConversationTurn(speaker="A", text=f"Fact {i}: the sky is blue"),),
            question=f"What color is the sky in fact {i}?",
            gold_answer="blue",
            category="test",
        )
        for i in range(n)
    ]


# --- build_judge tests ---

def test_build_judge_none() -> None:
    assert build_judge(None) is None


def test_build_judge_none_string() -> None:
    assert build_judge("none") is None


def test_build_judge_stub() -> None:
    j = build_judge("stub")
    assert isinstance(j, StubJudge)
    v = j.score(question="q", gold="g", pred="p")
    assert v.verdict == "correct"
    assert v.score == 1.0


def test_build_judge_unknown_raises() -> None:
    with pytest.raises(ValueError, match="unknown judge"):
        build_judge("unknown")


# --- missing dep / missing API key tests ---

def test_claude_judge_missing_dep(monkeypatch) -> None:
    """In a base install without anthropic, raises RuntimeError about the package."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="anthropic package"):
        ClaudeJudge()


def test_openai_judge_missing_dep(monkeypatch) -> None:
    """In a base install without openai, raises RuntimeError about the package."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="openai package"):
        OpenAIJudge()


# --- lazy import test ---

def test_claude_judge_does_not_import_anthropic_at_module_level() -> None:
    assert "anthropic" not in sys.modules


# --- runner integration tests ---

def test_run_benchmark_with_stub_judge() -> None:
    adapter = _MinimalAdapter()
    cases = _minimal_cases(2)
    adapter.reset(cases[0].case_id)
    adapter.ingest_turn(cases[0].case_id, cases[0].conversation[0])
    adapter.reset(cases[1].case_id)
    adapter.ingest_turn(cases[1].case_id, cases[1].conversation[0])

    report = run_benchmark(adapter=adapter, cases=cases, judge=StubJudge())
    assert report["scores"]["judge_score_mean"] == 1.0
    assert report["scores"]["judge_count"] == 2
    assert report["cases"][0]["judge"]["verdict"] == "correct"
    assert report["cases"][1]["judge"]["verdict"] == "correct"


def test_judge_error_caught_per_case() -> None:
    adapter = _MinimalAdapter()
    cases = _minimal_cases(1)
    adapter.reset(cases[0].case_id)
    adapter.ingest_turn(cases[0].case_id, cases[0].conversation[0])

    report = run_benchmark(adapter=adapter, cases=cases, judge=_ErrorJudge())
    assert "error" in report["cases"][0].get("judge", {})
    assert "simulated judge failure" in report["cases"][0]["judge"]["error"]


def test_run_benchmark_without_judge_no_judge_fields() -> None:
    """Default path (no judge) must not have judge_score_mean in scores."""
    adapter = _MinimalAdapter()
    cases = _minimal_cases(1)
    adapter.reset(cases[0].case_id)
    adapter.ingest_turn(cases[0].case_id, cases[0].conversation[0])

    report = run_benchmark(adapter=adapter, cases=cases)
    assert "judge_score_mean" not in report["scores"]
    assert "judge" not in report["cases"][0]


# --- CLI smoke ---

def test_cli_quickstart_with_stub_judge() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "benchmarks.external.locomo.run", "--quickstart", "--judge", "stub"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert "judge_score_mean" in data["scores"], f"keys: {list(data['scores'])}"

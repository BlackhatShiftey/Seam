from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

DEFAULT_JUDGE_PROMPT = """You are an impartial scorer for a memory-benchmark question.

Question: {question}
Gold answer: {gold}
System answer: {pred}

Score the system answer:
- "correct" if it conveys the same meaning as the gold answer (paraphrasing is fine)
- "partial" if it contains the right entity/fact but is incomplete or has minor errors
- "incorrect" if it is wrong, unsupported, or empty

Respond ONLY with strict JSON in this exact shape:
{{"verdict": "correct" | "partial" | "incorrect", "rationale": "one short sentence"}}"""

ABSTAINING_JUDGE_PROMPT = """You are an impartial scorer for a memory-benchmark question.

Question: {question}
Gold answer: {gold}
System answer: {pred}

Score the system answer:
- "correct" if it conveys the same meaning as the gold answer (paraphrasing is fine)
- "partial" if it contains the right entity/fact but is incomplete or has minor errors
- "incorrect" if it is wrong or unsupported by the context
- If the system answer is exactly "unknown", score as "abstain" — neither correct nor incorrect.

Respond ONLY with strict JSON in this exact shape:
{{"verdict": "correct" | "partial" | "incorrect" | "abstain", "rationale": "one short sentence"}}"""


@dataclass(frozen=True)
class JudgeVerdict:
    verdict: str           # "correct" | "partial" | "incorrect" | "abstain"
    score: float           # 1.0 / 0.5 / 0.0 (abstain: 0.0)
    rationale: str
    judge_name: str
    judge_model: str


class Judge(Protocol):
    name: str
    model: str
    def score(self, *, question: str, gold: str, pred: str) -> JudgeVerdict: ...


class StubJudge:
    """Deterministic smoke-test judge that never claims correctness."""
    name = "stub-informational-only"
    model = "stub-1"
    def score(self, *, question, gold, pred) -> JudgeVerdict:
        return JudgeVerdict("abstain", 0.0, "stub does not score correctness", self.name, self.model)


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(line for line in lines if not line.startswith("```"))
    return text.strip()


def _verdict_from_json_text(text: str, *, judge_name: str, judge_model: str) -> JudgeVerdict:
    try:
        data = json.loads(_strip_json_fence(text))
    except json.JSONDecodeError as exc:
        raise ValueError("judge returned unparseable JSON") from exc
    verdict = data.get("verdict")
    score_map = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0, "abstain": 0.0}
    if verdict not in score_map:
        raise ValueError("judge returned invalid verdict")
    rationale = str(data.get("rationale") or "judge returned no rationale")
    return JudgeVerdict(verdict, score_map[verdict], rationale, judge_name, judge_model)


class ClaudeJudge:
    name = "claude"

    def __init__(self, model: str | None = None):
        model = model or os.environ.get("SEAM_BENCH_JUDGE_MODEL", "claude-haiku-4-5-20251001")
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "--judge claude requires the anthropic package. "
                "Install with: pip install seam[bench-judge]"
            ) from exc
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("--judge claude requires ANTHROPIC_API_KEY in the environment")
        self.model = model
        self._client = Anthropic(api_key=api_key)

    def score(self, *, question, gold, pred) -> JudgeVerdict:
        prompt = DEFAULT_JUDGE_PROMPT.format(question=question, gold=gold, pred=pred)
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise RuntimeError(f"judge request failed: {type(exc).__name__}") from exc
        return _verdict_from_json_text(response.content[0].text, judge_name=self.name, judge_model=self.model)


class OpenAIJudge:
    name = "openai"

    def __init__(self, model: str | None = None):
        model = model or os.environ.get("SEAM_BENCH_JUDGE_MODEL", "gpt-4o-mini")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "--judge openai requires the openai package. "
                "Install with: pip install seam[bench-judge]"
            ) from exc
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("--judge openai requires OPENAI_API_KEY in the environment")
        self.model = model
        self._client = OpenAI(api_key=api_key)

    @staticmethod
    def _uses_completion_token_budget(model: str) -> bool:
        model_id = model.lower()
        return model_id.startswith(("gpt-5", "o1", "o3", "o4"))

    def score(self, *, question, gold, pred) -> JudgeVerdict:
        prompt = DEFAULT_JUDGE_PROMPT.format(question=question, gold=gold, pred=pred)
        try:
            request = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
            if self._uses_completion_token_budget(self.model):
                # GPT-5/o-series models reject max_tokens and can spend part of the
                # budget on hidden reasoning tokens. Minimal reasoning keeps judge
                # calls cheap and leaves room for the required JSON verdict.
                request["max_completion_tokens"] = 512
                request["reasoning_effort"] = "minimal"
            else:
                request["max_tokens"] = 256
            response = self._client.chat.completions.create(
                **request,
            )
        except Exception as exc:
            raise RuntimeError(f"judge request failed: {type(exc).__name__}") from exc
        text = response.choices[0].message.content or ""
        return _verdict_from_json_text(text, judge_name=self.name, judge_model=self.model)


def build_judge(name: str | None, model: str | None = None) -> Judge | None:
    if name is None or name == "none":
        return None
    if name == "stub":
        return StubJudge()
    if name == "claude":
        return ClaudeJudge(model=model)
    if name == "openai":
        return OpenAIJudge(model=model)
    raise ValueError(f"unknown judge: {name!r} (use stub|claude|openai|none)")

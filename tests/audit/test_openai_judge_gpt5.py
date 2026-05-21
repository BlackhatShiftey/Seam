"""Regression tests for OpenAI judge request construction."""

from benchmarks.external.common.judge import OpenAIJudge


class _Message:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class _FakeCompletions:
    def __init__(self, content: str = '{"verdict": "correct", "rationale": "matches"}'):
        self.content = content
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return _Response(self.content)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    def __init__(self, completions):
        self.chat = _FakeChat(completions)


def _judge_with_fake_client(model: str, completions: _FakeCompletions) -> OpenAIJudge:
    judge = object.__new__(OpenAIJudge)
    judge.model = model
    judge._client = _FakeClient(completions)
    return judge


def test_openai_judge_uses_gpt5_completion_token_parameter_and_json_mode():
    completions = _FakeCompletions()
    judge = _judge_with_fake_client("gpt-5-nano", completions)

    verdict = judge.score(question="Where?", gold="Tokyo", pred="Tokyo")

    assert verdict.verdict == "correct"
    assert verdict.score == 1.0
    assert completions.kwargs["model"] == "gpt-5-nano"
    assert completions.kwargs["max_completion_tokens"] == 512
    assert completions.kwargs["reasoning_effort"] == "minimal"
    assert "max_tokens" not in completions.kwargs
    assert completions.kwargs["response_format"] == {"type": "json_object"}


def test_openai_judge_preserves_legacy_max_tokens_for_non_reasoning_models():
    completions = _FakeCompletions()
    judge = _judge_with_fake_client("gpt-4o-mini", completions)

    verdict = judge.score(question="Where?", gold="Tokyo", pred="Tokyo")

    assert verdict.verdict == "correct"
    assert completions.kwargs["max_tokens"] == 256
    assert "max_completion_tokens" not in completions.kwargs
    assert completions.kwargs["response_format"] == {"type": "json_object"}


def test_openai_judge_surfaces_request_error_type_without_secret_values():
    class BadRequestError(RuntimeError):
        pass

    class FailingCompletions(_FakeCompletions):
        def create(self, **kwargs):
            self.kwargs = kwargs
            raise BadRequestError("unsupported parameter")

    completions = FailingCompletions()
    judge = _judge_with_fake_client("gpt-5-nano", completions)

    verdict = judge.score(question="Where?", gold="Tokyo", pred="Tokyo")

    assert verdict.verdict == "incorrect"
    assert verdict.score == 0.0
    assert "BadRequestError" in verdict.rationale

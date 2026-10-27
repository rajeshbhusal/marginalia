import json
from types import SimpleNamespace

import pytest

from app.course.schemas import DiagnosticQuizDraft
from app.llm.base import LLMRequest, Message
from app.llm.exceptions import LLMOutputError, LLMRefusalError
from app.llm.providers.openai import OpenAIProvider
from app.settings import settings

QUIZ = {
    "questions": [
        {"question": "2 + 2?", "options": ["3", "4", "5"], "correct_option": 1, "concept": "sums"}
    ]
}


def make_response(text="", parsed=None, status="completed", output=None, incomplete=None):
    if output is None:
        output = [
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text=text, annotations=[])],
            )
        ]
    return SimpleNamespace(
        error=None,
        status=status,
        incomplete_details=SimpleNamespace(reason=incomplete) if incomplete else None,
        output=output,
        output_text=text,
        output_parsed=parsed,
    )


class FakeResponseStream:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self._events()

    async def _events(self):
        for i in range(0, len(self.response.output_text), 9):
            chunk = self.response.output_text[i : i + 9]
            yield SimpleNamespace(type="response.output_text.delta", delta=chunk)

    async def get_final_response(self):
        return self.response


class FakeOpenAI:
    def __init__(self, response=None, completion=None):
        self.calls: list[tuple[str, dict]] = []
        self._response = response
        self._completion = completion
        self.responses = SimpleNamespace(stream=self._stream, create=self._create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    def _stream(self, **params):
        self.calls.append(("responses.stream", params))
        return FakeResponseStream(self._response)

    async def _create(self, **params):
        self.calls.append(("responses.create", params))
        return self._response

    async def _parse(self, **params):
        self.calls.append(("chat.completions.parse", params))
        return self._completion


def make_request(**overrides) -> LLMRequest:
    fields = {
        "task": "diagnostics",
        "system": "You write quizzes.",
        "messages": [Message("user", "Quiz me on arithmetic")],
        "effort": "medium",
    }
    return LLMRequest(**(fields | overrides))


async def test_responses_api_structured_output_with_reasoning_effort():
    text = json.dumps(QUIZ)
    client = FakeOpenAI(
        response=make_response(text, parsed=DiagnosticQuizDraft.model_validate(QUIZ))
    )
    provider = OpenAIProvider("gpt-6.1-sol", client=client)
    partials: list[str] = []

    async def on_partial(partial: str):
        partials.append(partial)

    result = await provider.generate(make_request(), DiagnosticQuizDraft, on_partial)

    assert result.questions[0].options == ["3", "4", "5"]
    method, params = client.calls[0]
    assert method == "responses.stream"
    assert params["text_format"] is DiagnosticQuizDraft
    assert params["instructions"] == "You write quizzes."
    assert params["reasoning"] == {"effort": "medium"}
    assert "temperature" not in params
    assert partials[-1] == text


async def test_incomplete_and_refused_responses_raise():
    truncated = make_response(status="incomplete", incomplete="max_output_tokens")
    provider = OpenAIProvider("gpt-6.1-sol", client=FakeOpenAI(response=truncated))
    with pytest.raises(LLMOutputError):
        await provider.generate(make_request(), DiagnosticQuizDraft)

    refusal = make_response(
        output=[
            SimpleNamespace(
                type="message", content=[SimpleNamespace(type="refusal", refusal="No.")]
            )
        ]
    )
    provider = OpenAIProvider("gpt-6.1-sol", client=FakeOpenAI(response=refusal))
    with pytest.raises(LLMRefusalError):
        await provider.generate(make_request(), DiagnosticQuizDraft)


async def test_chat_mode_targets_openai_compatible_servers(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_MODE", "chat")
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", "http://localhost:8000/v1")
    message = SimpleNamespace(refusal=None, parsed=DiagnosticQuizDraft.model_validate(QUIZ))
    completion = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    client = FakeOpenAI(completion=completion)
    provider = OpenAIProvider("llama-4", client=client)

    result = await provider.generate(make_request(), DiagnosticQuizDraft)

    assert result.questions[0].correct_option == 1
    assert not provider.supports_web_search
    method, params = client.calls[0]
    assert method == "chat.completions.parse"
    assert params["response_format"] is DiagnosticQuizDraft
    assert params["messages"][0] == {"role": "system", "content": "You write quizzes."}


async def test_research_uses_web_search_and_collects_url_citations():
    annotation = SimpleNamespace(
        type="url_citation", url="https://example.com/bayes", title="Bayes' theorem"
    )
    response = make_response(
        text="- Published in 1763.",
        output=[
            SimpleNamespace(type="web_search_call"),
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text", text="- Published in 1763.", annotations=[annotation]
                    )
                ],
            ),
        ],
    )
    client = FakeOpenAI(response=response)
    provider = OpenAIProvider("gpt-6.1-sol", client=client)

    result = await provider.research(make_request(task="research"), max_searches=3)

    assert result.notes == "- Published in 1763."
    assert [s.url for s in result.sources] == ["https://example.com/bayes"]
    method, params = client.calls[0]
    assert params["tools"] == [{"type": "web_search"}]
    assert params["max_tool_calls"] == 3

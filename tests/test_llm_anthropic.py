import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from anthropic.types.beta import BetaMessage

from app.course.schemas import DiagnosticQuizDraft
from app.llm.base import LLMRequest, Message
from app.llm.exceptions import LLMOutputError, LLMRateLimitError, LLMRefusalError
from app.llm.providers.anthropic import (
    REFUSAL_FALLBACKS_BETA,
    WEB_SEARCH_TOOL,
    AnthropicProvider,
)
from app.settings import settings

QUIZ = {
    "questions": [
        {"question": "2 + 2?", "options": ["3", "4", "5"], "correct_option": 1, "concept": "sums"}
    ]
}


def make_message(content, stop_reason="end_turn", stop_details=None) -> BetaMessage:
    return BetaMessage.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "stop_details": stop_details,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        }
    )


class FakeStream:
    """Mimics the SDK's beta message stream: text events, then the final message."""

    def __init__(self, message: BetaMessage):
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self._events()

    async def _events(self):
        for block in self.message.content:
            if block.type == "text":
                for i in range(0, len(block.text), 7):
                    yield SimpleNamespace(type="text", text=block.text[i : i + 7])

    async def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, *results):
        self.calls: list[dict] = []
        self._results = list(results)
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **params):
        self.calls.append(params)
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return FakeStream(result)


def make_request(**overrides) -> LLMRequest:
    fields = {
        "task": "diagnostics",
        "system": "You write quizzes.",
        "messages": [Message("user", "Quiz me on arithmetic")],
        "effort": "low",
    }
    return LLMRequest(**(fields | overrides))


async def test_generate_uses_structured_outputs_effort_and_refusal_fallbacks():
    client = FakeClient(make_message([{"type": "text", "text": json.dumps(QUIZ)}]))
    provider = AnthropicProvider("claude-opus-5-5", client=client)
    partials: list[str] = []

    async def on_partial(text: str):
        partials.append(text)

    result = await provider.generate(make_request(), DiagnosticQuizDraft, on_partial)

    assert result.questions[0].correct_option == 1
    params = client.calls[0]
    assert params["model"] == "claude-opus-5-5"
    assert params["output_config"]["effort"] == "low"
    output_format = params["output_config"]["format"]
    assert output_format["type"] == "json_schema"
    assert output_format["schema"]["additionalProperties"] is False
    assert params["betas"] == [REFUSAL_FALLBACKS_BETA]
    assert params["fallbacks"] == "default"
    # The 2026-10-21 API version rejects sampling parameters, and thinking is adaptive by default
    assert not {"temperature", "top_p", "top_k", "thinking"} & params.keys()
    assert len(partials) > 1 and partials[-1] == json.dumps(QUIZ)


async def test_output_split_by_a_server_side_fallback_is_joined():
    text = json.dumps(QUIZ)
    message = make_message(
        [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "text", "text": text[:20]},
            {
                "type": "fallback",
                "from": {"model": "claude-opus-5-5"},
                "to": {"model": "claude-opus-4-8"},
                "trigger": {"type": "refusal", "category": "bio"},
            },
            {"type": "text", "text": text[20:]},
        ]
    )
    provider = AnthropicProvider("claude-opus-5-5", client=FakeClient(message))

    result = await provider.generate(make_request(), DiagnosticQuizDraft)

    assert result == DiagnosticQuizDraft.model_validate(QUIZ)


async def test_refusal_raises_a_refusal_error():
    message = make_message(
        [],
        stop_reason="refusal",
        stop_details={"type": "refusal", "category": "cyber", "explanation": None},
    )
    provider = AnthropicProvider("claude-opus-5-5", client=FakeClient(message))

    with pytest.raises(LLMRefusalError, match="cyber"):
        await provider.generate(make_request(), DiagnosticQuizDraft)


async def test_truncated_output_raises_an_output_error():
    message = make_message([{"type": "text", "text": '{"questions": ['}], stop_reason="max_tokens")
    provider = AnthropicProvider("claude-opus-5-5", client=FakeClient(message))

    with pytest.raises(LLMOutputError):
        await provider.generate(make_request(), DiagnosticQuizDraft)


async def test_cached_system_prompt_and_disabled_fallbacks(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_REFUSAL_FALLBACKS", False)
    client = FakeClient(make_message([{"type": "text", "text": "  Here is why.  "}]))
    provider = AnthropicProvider("claude-opus-5-5", client=client)

    reply = await provider.generate_text(make_request(cache_system=True))

    assert reply == "Here is why."
    params = client.calls[0]
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "fallbacks" not in params and "betas" not in params


async def test_models_without_effort_support_omit_it():
    client = FakeClient(make_message([{"type": "text", "text": "ok"}]))
    provider = AnthropicProvider("claude-haiku-4-5", client=client)

    await provider.generate_text(make_request())

    assert "output_config" not in client.calls[0]


async def test_research_uses_web_search_resumes_paused_turns_and_collects_citations():
    paused = make_message(
        [
            {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {}},
            {
                "type": "web_search_tool_result",
                "tool_use_id": "srvtoolu_1",
                "content": [
                    {
                        "type": "web_search_result",
                        "url": "https://example.com/search-hit",
                        "title": "Search hit",
                        "encrypted_content": "x",
                        "page_age": None,
                    }
                ],
            },
        ],
        stop_reason="pause_turn",
    )
    finished = make_message(
        [
            {"type": "text", "text": "- Bayes' theorem relates conditional probabilities"},
            {
                "type": "text",
                "text": " (first published in 1763).",
                "citations": [
                    {
                        "type": "web_search_result_location",
                        "url": "https://example.com/bayes",
                        "title": "Bayes' theorem",
                        "cited_text": "published in 1763",
                        "encrypted_index": "x",
                    }
                ],
            },
        ]
    )
    client = FakeClient(paused, finished)
    provider = AnthropicProvider("claude-opus-5-5", client=client)

    result = await provider.research(make_request(task="research"), max_searches=2)

    assert result.notes == (
        "- Bayes' theorem relates conditional probabilities (first published in 1763)."
    )
    assert [(s.title, s.url) for s in result.sources] == [
        ("Bayes' theorem", "https://example.com/bayes")
    ]
    first, second = client.calls
    assert first["tools"] == [{"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": 2}]
    # The paused turn is sent back unchanged so the server can resume it
    assert second["messages"][-1] == {"role": "assistant", "content": paused.content}


async def test_api_errors_become_learner_friendly_errors():
    response = httpx2.Response(429, request=httpx2.Request("POST", "https://api.anthropic.com"))
    error = anthropic.RateLimitError("rate limited", response=response, body=None)
    provider = AnthropicProvider("claude-opus-5-5", client=FakeClient(error))

    with pytest.raises(LLMRateLimitError):
        await provider.generate_text(make_request())

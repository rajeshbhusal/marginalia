"""Claude through the Anthropic SDK (the default provider)."""

import anthropic
from pydantic import ValidationError

from app.llm.base import LLMRequest, PartialCallback, ResearchResult, SchemaT, Source
from app.llm.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMOutputError,
    LLMRateLimitError,
    LLMRefusalError,
)
from app.settings import settings

# Claude's safety classifiers can decline a request. With server-side fallbacks the API retries
# a declined request on the model Anthropic recommends for that refusal category; on models
# without fallbacks the request simply runs as usual.
REFUSAL_FALLBACKS_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH_TOOL = "web_search_20260209"
# Earlier models that reject output_config.effort
MODELS_WITHOUT_EFFORT = (
    "claude-3",
    "claude-haiku-4-5",
    "claude-sonnet-4-0",
    "claude-sonnet-4-5",
    "claude-opus-4-0",
    "claude-opus-4-1",
)
# A server-side tool loop can pause (stop_reason "pause_turn"); resume it at most this often
MAX_PAUSE_TURN_RESUMES = 3


class AnthropicProvider:
    name = "anthropic"
    supports_web_search = True

    def __init__(self, model: str, client: anthropic.AsyncAnthropic | None = None):
        self.model = model
        self._client = client

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            try:
                # Without ANTHROPIC_API_KEY the SDK falls back to its own credential lookup,
                # such as a profile from `ant auth login`.
                self._client = anthropic.AsyncAnthropic(
                    api_key=settings.ANTHROPIC_API_KEY or None,
                    base_url=settings.ANTHROPIC_BASE_URL or None,
                    timeout=settings.LLM_TIMEOUT,
                    max_retries=settings.LLM_MAX_RETRIES,
                )
            except anthropic.AnthropicError as e:
                raise LLMConfigurationError(
                    "No Anthropic credentials found. Set ANTHROPIC_API_KEY in .env."
                ) from e
        return self._client

    async def generate(
        self,
        request: LLMRequest,
        schema: type[SchemaT],
        on_partial: PartialCallback | None = None,
    ) -> SchemaT:
        params = self._params(request)
        params.setdefault("output_config", {})["format"] = {
            "type": "json_schema",
            "schema": anthropic.transform_schema(schema),
        }
        message = await self._stream(params, on_partial)
        try:
            return schema.model_validate_json(_text_of(message))
        except ValidationError as e:
            raise LLMOutputError("Claude's response didn't match the expected format.") from e

    async def generate_text(self, request: LLMRequest) -> str:
        message = await self._stream(self._params(request))
        return _text_of(message).strip()

    async def research(self, request: LLMRequest, max_searches: int) -> ResearchResult:
        params = self._params(request)
        params["tools"] = [
            {"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": max_searches}
        ]

        content = []
        for _ in range(MAX_PAUSE_TURN_RESUMES + 1):
            message = await self._stream(params)
            content.extend(message.content)
            if message.stop_reason != "pause_turn":
                break
            # Send the paused turn back unchanged and the API resumes where it stopped
            params["messages"] = [
                *params["messages"],
                {"role": "assistant", "content": message.content},
            ]

        notes = "".join(block.text for block in content if block.type == "text").strip()
        return ResearchResult(notes=notes, sources=_sources_of(content))

    def _params(self, request: LLMRequest) -> dict:
        system = {"type": "text", "text": request.system}
        if request.cache_system:
            system["cache_control"] = {"type": "ephemeral"}
        params = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "system": [system],
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        # Thinking is adaptive by default on current models; effort controls how much they think
        if not self.model.startswith(MODELS_WITHOUT_EFFORT):
            params["output_config"] = {"effort": request.effort}
        if settings.ANTHROPIC_REFUSAL_FALLBACKS:
            params["betas"] = [REFUSAL_FALLBACKS_BETA]
            params["fallbacks"] = "default"
        return params

    async def _stream(self, params: dict, on_partial: PartialCallback | None = None):
        # Always stream: responses with thinking can be long, and streaming avoids HTTP timeouts.
        try:
            async with self.client.beta.messages.stream(**params) as stream:
                if on_partial is not None:
                    text = ""
                    async for event in stream:
                        if event.type == "text":
                            text += event.text
                            await on_partial(text)
                message = await stream.get_final_message()
        except anthropic.APIError as e:
            raise _translate_error(e, self.model) from e
        except anthropic.AnthropicError as e:
            raise LLMConfigurationError(
                "No Anthropic credentials found. Set ANTHROPIC_API_KEY in .env."
            ) from e

        if message.stop_reason == "refusal":
            category = message.stop_details.category if message.stop_details else None
            detail = f" ({category})" if category else ""
            raise LLMRefusalError(f"Claude declined to answer this request{detail}.")
        if message.stop_reason == "max_tokens":
            raise LLMOutputError("Claude's response was cut off before it finished.")
        return message


def _text_of(message) -> str:
    # Read blocks by type: a response can also hold thinking blocks and, after a server-side
    # fallback, a "fallback" marker between the text the first and second model wrote.
    return "".join(block.text for block in message.content if block.type == "text")


def _sources_of(content) -> list[Source]:
    sources: dict[str, str] = {}
    for block in content:
        if block.type == "text":
            for citation in block.citations or []:
                url = getattr(citation, "url", None)
                if url:
                    sources.setdefault(url, getattr(citation, "title", None) or url)
    if not sources:
        # Nothing was cited, so fall back to the top search results
        for block in content:
            if block.type == "web_search_tool_result" and isinstance(block.content, list):
                for result in block.content[:5]:
                    sources.setdefault(result.url, result.title or result.url)
    return [Source(title=title, url=url) for url, title in sources.items()]


def _translate_error(error: anthropic.APIError, model: str) -> LLMError:
    if isinstance(error, anthropic.AuthenticationError):
        return LLMConfigurationError("Anthropic rejected the API key. Check ANTHROPIC_API_KEY.")
    if isinstance(error, anthropic.PermissionDeniedError):
        return LLMConfigurationError("This Anthropic API key isn't allowed to make this request.")
    if isinstance(error, anthropic.NotFoundError):
        return LLMConfigurationError(f"Claude model '{model}' wasn't found. Check LLM_MODEL.")
    if isinstance(error, anthropic.RateLimitError):
        return LLMRateLimitError("Claude is rate limited right now. Try again in a minute.")
    if isinstance(error, anthropic.BadRequestError):
        return LLMError(f"Claude rejected the request: {error.message}")
    if isinstance(error, anthropic.APIStatusError):
        return LLMError(f"Claude returned an error ({error.status_code}). Try again shortly.")
    if isinstance(error, anthropic.APITimeoutError):
        return LLMError("Claude took too long to respond. Try again.")
    if isinstance(error, anthropic.APIConnectionError):
        return LLMError("Couldn't reach the Anthropic API. Check your network connection.")
    return LLMError(f"Claude request failed: {error}")

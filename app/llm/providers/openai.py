"""OpenAI models, or any OpenAI-compatible server (vLLM, Ollama, ...) in chat mode."""

import openai

from app.llm.base import LLMRequest, PartialCallback, ResearchResult, SchemaT, Source
from app.llm.exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMOutputError,
    LLMRateLimitError,
    LLMRefusalError,
)
from app.settings import settings


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, client: openai.AsyncOpenAI | None = None):
        self.model = model
        self._client = client
        # "responses" uses OpenAI's Responses API; "chat" uses Chat Completions, which
        # OpenAI-compatible servers implement.
        self.mode = settings.OPENAI_API_MODE
        # Built-in web search only exists on OpenAI's own Responses API
        self.supports_web_search = self.mode == "responses" and not settings.OPENAI_BASE_URL

    @property
    def client(self) -> openai.AsyncOpenAI:
        if self._client is None:
            try:
                self._client = openai.AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY or None,
                    base_url=settings.OPENAI_BASE_URL or None,
                    timeout=settings.LLM_TIMEOUT,
                    max_retries=settings.LLM_MAX_RETRIES,
                )
            except openai.OpenAIError as e:
                raise LLMConfigurationError("No OpenAI API key found. Set OPENAI_API_KEY.") from e
        return self._client

    async def generate(
        self,
        request: LLMRequest,
        schema: type[SchemaT],
        on_partial: PartialCallback | None = None,
    ) -> SchemaT:
        if self.mode == "chat":
            return await self._chat_parse(request, schema)

        try:
            async with self.client.responses.stream(
                **self._params(request), text_format=schema
            ) as stream:
                if on_partial is not None:
                    text = ""
                    async for event in stream:
                        if event.type == "response.output_text.delta":
                            text += event.delta
                            await on_partial(text)
                response = await stream.get_final_response()
        except openai.APIError as e:
            raise _translate_error(e, self.model) from e

        _check_response(response)
        if response.output_parsed is None:
            raise LLMOutputError("The model's response didn't match the expected format.")
        return response.output_parsed

    async def generate_text(self, request: LLMRequest) -> str:
        try:
            if self.mode == "chat":
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=_chat_messages(request),
                    max_completion_tokens=request.max_tokens,
                )
                choice = completion.choices[0]
                if choice.finish_reason == "length":
                    raise LLMOutputError("The model's response was cut off before it finished.")
                return (choice.message.content or "").strip()

            response = await self.client.responses.create(**self._params(request))
        except openai.APIError as e:
            raise _translate_error(e, self.model) from e
        _check_response(response)
        return response.output_text.strip()

    async def research(self, request: LLMRequest, max_searches: int) -> ResearchResult:
        try:
            response = await self.client.responses.create(
                **self._params(request),
                tools=[{"type": "web_search"}],
                max_tool_calls=max_searches,
            )
        except openai.APIError as e:
            raise _translate_error(e, self.model) from e
        _check_response(response)

        sources: dict[str, str] = {}
        for item in response.output:
            if item.type != "message":
                continue
            for part in item.content:
                for annotation in getattr(part, "annotations", None) or []:
                    if annotation.type == "url_citation":
                        sources.setdefault(annotation.url, annotation.title or annotation.url)
        return ResearchResult(
            notes=response.output_text.strip(),
            sources=[Source(title=title, url=url) for url, title in sources.items()],
        )

    def _params(self, request: LLMRequest) -> dict:
        return {
            "model": self.model,
            "instructions": request.system,
            "input": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_output_tokens": request.max_tokens,
            "reasoning": {"effort": request.effort},
        }

    async def _chat_parse(self, request: LLMRequest, schema: type[SchemaT]) -> SchemaT:
        try:
            completion = await self.client.chat.completions.parse(
                model=self.model,
                messages=_chat_messages(request),
                response_format=schema,
                max_completion_tokens=request.max_tokens,
            )
        except openai.LengthFinishReasonError as e:
            raise LLMOutputError("The model's response was cut off before it finished.") from e
        except openai.ContentFilterFinishReasonError as e:
            raise LLMRefusalError("The model's content filter blocked this response.") from e
        except openai.APIError as e:
            raise _translate_error(e, self.model) from e

        message = completion.choices[0].message
        if message.refusal:
            raise LLMRefusalError(f"The model declined to answer: {message.refusal}")
        if message.parsed is None:
            raise LLMOutputError("The model's response didn't match the expected format.")
        return message.parsed


def _chat_messages(request: LLMRequest) -> list[dict]:
    return [
        {"role": "system", "content": request.system},
        *({"role": m.role, "content": m.content} for m in request.messages),
    ]


def _check_response(response) -> None:
    if response.error:
        raise LLMError(f"The model returned an error: {response.error.message}")
    if response.status == "incomplete":
        reason = response.incomplete_details.reason if response.incomplete_details else None
        if reason == "content_filter":
            raise LLMRefusalError("The model's content filter blocked this response.")
        raise LLMOutputError("The model's response was cut off before it finished.")
    for item in response.output:
        if item.type == "message":
            for part in item.content:
                if part.type == "refusal":
                    raise LLMRefusalError(f"The model declined to answer: {part.refusal}")


def _translate_error(error: openai.APIError, model: str) -> LLMError:
    if isinstance(error, openai.AuthenticationError):
        return LLMConfigurationError("OpenAI rejected the API key. Check OPENAI_API_KEY.")
    if isinstance(error, openai.PermissionDeniedError):
        return LLMConfigurationError("This OpenAI API key isn't allowed to make this request.")
    if isinstance(error, openai.NotFoundError):
        return LLMConfigurationError(f"Model '{model}' wasn't found. Check LLM_MODEL.")
    if isinstance(error, openai.RateLimitError):
        return LLMRateLimitError("The model is rate limited right now. Try again in a minute.")
    if isinstance(error, openai.BadRequestError):
        return LLMError(f"The model rejected the request: {error.message}")
    if isinstance(error, openai.APIStatusError):
        return LLMError(f"The model returned an error ({error.status_code}). Try again shortly.")
    if isinstance(error, openai.APITimeoutError):
        return LLMError("The model took too long to respond. Try again.")
    if isinstance(error, openai.APIConnectionError):
        return LLMError("Couldn't reach the model's API. Check OPENAI_BASE_URL and your network.")
    return LLMError(f"Model request failed: {error}")

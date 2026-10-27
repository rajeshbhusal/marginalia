"""Entry points the rest of the app uses to call the configured model."""

import json
import logging
import time

from app.llm.base import LLMProvider, LLMRequest, PartialCallback, ResearchResult, SchemaT
from app.llm.cache import cache_key, get_cached, store_cached
from app.llm.exceptions import LLMConfigurationError
from app.settings import settings

logger = logging.getLogger(__name__)

_provider: LLMProvider | None = None
_override: LLMProvider | None = None


def create_provider() -> LLMProvider:
    match settings.LLM_PROVIDER:
        case "anthropic":
            from app.llm.providers.anthropic import AnthropicProvider

            return AnthropicProvider(settings.default_model)
        case "openai":
            from app.llm.providers.openai import OpenAIProvider

            return OpenAIProvider(settings.default_model)
        case "fake":
            from app.llm.providers.fake import FakeProvider

            return FakeProvider(settings.default_model, delay=settings.FAKE_LLM_DELAY)
    raise LLMConfigurationError(f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'")


def get_llm() -> LLMProvider:
    global _provider
    if _override is not None:
        return _override
    if _provider is None:
        _provider = create_provider()
    return _provider


def set_llm(provider: LLMProvider | None) -> None:
    """Route every call to `provider` (used by tests); None restores the configured provider."""
    global _override
    _override = provider


async def generate(
    request: LLMRequest,
    schema: type[SchemaT],
    *,
    on_partial: PartialCallback | None = None,
    use_cache: bool = True,
) -> SchemaT:
    """Ask the model for a response that matches `schema`."""
    llm = get_llm()
    key = None
    if use_cache and settings.LLM_CACHE:
        schema_json = json.dumps(schema.model_json_schema(), sort_keys=True)
        key = cache_key(llm.name, llm.model, request, schema_json)
        if (cached := await get_cached(key)) is not None:
            logger.info("LLM %s: cache hit", request.task)
            return schema.model_validate_json(cached)

    started = time.monotonic()
    result = await llm.generate(request, schema, on_partial=on_partial)
    logger.info("LLM %s: %s took %.1fs", request.task, llm.model, time.monotonic() - started)

    if key:
        await store_cached(key, llm.name, llm.model, request.task, result.model_dump_json())
    return result


async def generate_text(request: LLMRequest) -> str:
    """Ask the model for a free-form markdown response."""
    llm = get_llm()
    started = time.monotonic()
    text = await llm.generate_text(request)
    logger.info("LLM %s: %s took %.1fs", request.task, llm.model, time.monotonic() - started)
    return text


async def research(request: LLMRequest, max_searches: int) -> ResearchResult | None:
    """Research with the provider's web search, or return None if it has none."""
    llm = get_llm()
    if not llm.supports_web_search:
        return None
    started = time.monotonic()
    result = await llm.research(request, max_searches)
    logger.info("LLM %s: %s took %.1fs", request.task, llm.model, time.monotonic() - started)
    return result

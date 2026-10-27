"""Provider-neutral types for talking to a language model."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

from app.settings import Effort

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# Called with the full text generated so far while a structured response streams in
PartialCallback = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class LLMRequest:
    # What the call is for, e.g. "section"; used for logging, caching and the fake provider
    task: str
    system: str
    messages: list[Message]
    effort: Effort = "medium"
    max_tokens: int = 16_000  # Includes the model's thinking, so leave room beyond the answer
    # Mark the system prompt as a prompt-caching breakpoint. Worth it when several requests share
    # a long system prompt, like tutor questions about the same section.
    cache_system: bool = False
    # Structured facts about the request for the offline fake provider. Never sent to an API.
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Source:
    title: str
    url: str


@dataclass
class ResearchResult:
    notes: str  # Markdown
    sources: list[Source]


class LLMProvider(Protocol):
    name: str
    model: str
    supports_web_search: bool

    async def generate(
        self,
        request: LLMRequest,
        schema: type[SchemaT],
        on_partial: PartialCallback | None = None,
    ) -> SchemaT:
        """Return a response that conforms to `schema` (structured outputs)."""
        ...

    async def generate_text(self, request: LLMRequest) -> str:
        """Return a free-form (markdown) response."""
        ...

    async def research(self, request: LLMRequest, max_searches: int) -> ResearchResult:
        """Search the web and return notes with their sources."""
        ...

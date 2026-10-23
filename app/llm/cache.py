import hashlib
import json

from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, select

from app.db.base_model import BaseDBModel
from app.db.session import get_session
from app.llm.base import LLMRequest


class LLMCacheEntry(BaseDBModel, table=True):
    """A stored model response, reused for identical requests when LLM_CACHE is on."""

    __tablename__ = "llm_cache"
    __table_args__ = (UniqueConstraint("key", name="uq_llm_cache_key"),)

    key: str = Field(index=True)
    provider: str
    model: str
    task: str
    response: str = Field(sa_type=Text)


def cache_key(provider: str, model: str, request: LLMRequest, kind: str) -> str:
    payload = json.dumps(
        {
            "provider": provider,
            "model": model,
            "kind": kind,  # e.g. the output schema's JSON schema, or "text"
            "task": request.task,
            "system": request.system,
            "messages": [[m.role, m.content] for m in request.messages],
            "effort": request.effort,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def get_cached(key: str) -> str | None:
    async with get_session() as db:
        result = await db.exec(select(LLMCacheEntry.response).where(LLMCacheEntry.key == key))
        return result.first()


async def store_cached(key: str, provider: str, model: str, task: str, response: str) -> None:
    async with get_session() as db:
        db.add(LLMCacheEntry(key=key, provider=provider, model=model, task=task, response=response))
        try:
            await db.commit()
        except IntegrityError:
            # Another request stored the same response first
            await db.rollback()

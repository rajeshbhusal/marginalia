"""Imports every table model so SQLModel.metadata is complete (used by Alembic and tests)."""

from app.course.models import Course, Section  # noqa: F401
from app.db.base_model import BaseDBModel, UUIDModel  # noqa: F401
from app.llm.cache import LLMCacheEntry  # noqa: F401
from app.tutor.models import Thread, ThreadMessage  # noqa: F401

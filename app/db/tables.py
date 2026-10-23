"""Imports every table model so SQLModel.metadata is complete (used by Alembic and tests)."""

from app.db.base_model import BaseDBModel, UUIDModel  # noqa: F401

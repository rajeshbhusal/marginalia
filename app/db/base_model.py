import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, TypeDecorator
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime:
    return datetime.now(UTC)


class TZDateTime(TypeDecorator):
    """Stores datetimes as UTC and always returns timezone-aware values (SQLite included)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            value = value.astimezone(UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            value = value.astimezone(UTC)
        return value


class TimestampedModel(SQLModel):
    created: datetime = Field(default_factory=get_utc_now, sa_type=TZDateTime)
    updated: datetime = Field(
        default_factory=get_utc_now,
        sa_type=TZDateTime,
        sa_column_kwargs={"onupdate": get_utc_now},
    )


class BaseDBModel(TimestampedModel):
    id: int | None = Field(default=None, primary_key=True)


class UUIDModel(TimestampedModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

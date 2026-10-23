import secrets
from enum import StrEnum


class BaseEnum(StrEnum):
    pass


def short_id(prefix: str) -> str:
    """A short random id for items stored inside JSON documents, like blocks."""
    return f"{prefix}_{secrets.token_hex(6)}"

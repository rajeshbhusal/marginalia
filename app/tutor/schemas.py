import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


class ThreadCreate(BaseModel):
    block_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    # Kept exactly as selected (not stripped) so it lines up with its prefix and suffix
    quote: Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(_not_blank)]
    # A little of the text before and after the quote, to find the passage again
    prefix: str = Field(default="", max_length=200)
    suffix: str = Field(default="", max_length=200)
    question: Question


class MessageCreate(BaseModel):
    content: Question


class ThreadUpdate(BaseModel):
    resolved: bool


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["learner", "tutor"]
    content: str
    created: datetime


class ThreadOut(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    block_id: str
    quote: str
    prefix: str
    suffix: str
    resolved: bool
    created: datetime
    messages: list[MessageOut]

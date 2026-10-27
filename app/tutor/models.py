import uuid

from sqlalchemy import Text
from sqlmodel import Field

from app.db.base_model import UUIDModel


class Thread(UUIDModel, table=True):
    """A margin thread: questions anchored to a highlighted passage in one block."""

    __tablename__ = "thread"

    course_id: uuid.UUID = Field(foreign_key="course.id", index=True, ondelete="CASCADE")
    section_id: uuid.UUID = Field(foreign_key="section.id", index=True, ondelete="CASCADE")
    block_id: str
    # The highlighted text, plus a little text either side so the client can find it again
    quote: str = Field(sa_type=Text)
    prefix: str = Field(default="", sa_type=Text)
    suffix: str = Field(default="", sa_type=Text)
    resolved: bool = False


class ThreadMessage(UUIDModel, table=True):
    __tablename__ = "thread_message"

    thread_id: uuid.UUID = Field(foreign_key="thread.id", index=True, ondelete="CASCADE")
    role: str  # "learner" or "tutor"
    content: str = Field(sa_type=Text)

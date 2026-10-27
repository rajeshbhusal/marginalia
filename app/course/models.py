import uuid
from datetime import datetime

from sqlalchemy import JSON, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.course.schemas import CourseStatus, SectionStatus
from app.db.base_model import TZDateTime, UUIDModel

# JSONB on Postgres (Supabase included), plain JSON elsewhere (SQLite in tests)
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Course(UUIDModel, table=True):
    __tablename__ = "course"

    title: str
    description: str = Field(default="", sa_type=Text)
    goal: str = Field(sa_type=Text)
    depth: str
    learning_style: str
    background: str = Field(default="", sa_type=Text)
    status: str = CourseStatus.diagnostic
    error: str | None = Field(default=None, sa_type=Text)
    # JSON documents; see DiagnosticQuestion, DiagnosticAnswer, LearnerProfile and OutlineModule
    diagnostics: list[dict] = Field(default_factory=list, sa_type=JSONType)
    answers: list[dict] = Field(default_factory=list, sa_type=JSONType)
    profile: dict | None = Field(default=None, sa_type=JSONType)
    outline: list[dict] = Field(default_factory=list, sa_type=JSONType)
    model: str  # The model that planned the course
    current_section_id: uuid.UUID | None = None


class Section(UUIDModel, table=True):
    __tablename__ = "section"

    course_id: uuid.UUID = Field(foreign_key="course.id", index=True, ondelete="CASCADE")
    position: int  # Order within the whole course
    module_index: int
    module_title: str
    title: str
    summary: str = Field(default="", sa_type=Text)
    status: str = SectionStatus.pending
    stage: str | None = None  # Progress while generating: queued, researching or writing
    blocks: list[dict] = Field(default_factory=list, sa_type=JSONType)  # See app.course.blocks
    recap: str = Field(default="", sa_type=Text)
    research: dict | None = Field(default=None, sa_type=JSONType)  # See ResearchNotes
    error: str | None = Field(default=None, sa_type=Text)
    model: str | None = None
    generation_started_at: datetime | None = Field(default=None, sa_type=TZDateTime)
    generated_at: datetime | None = Field(default=None, sa_type=TZDateTime)
    completed_at: datetime | None = Field(default=None, sa_type=TZDateTime)

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.course.blocks import Block, BlockDraft
from app.llm.schema import DraftModel
from app.util import BaseEnum


class Depth(BaseEnum):
    overview = "overview"
    practitioner = "practitioner"
    rigorous = "rigorous"


class LearningStyle(BaseEnum):
    visual = "visual"
    reading = "reading"
    hands_on = "hands_on"
    intuition = "intuition"


class CourseStatus(BaseEnum):
    diagnostic = "diagnostic"  # Waiting for the learner to answer the diagnostic questions
    planning = "planning"  # The outline is being written
    planning_failed = "planning_failed"
    outline_ready = "outline_ready"  # The learner can edit the outline before starting
    in_progress = "in_progress"


class SectionStatus(BaseEnum):
    pending = "pending"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class SectionStage(BaseEnum):
    queued = "queued"
    researching = "researching"
    writing = "writing"


# --- Diagnostics -----------------------------------------------------------------------------


class DiagnosticQuestionDraft(DraftModel):
    question: str
    options: list[str] = Field(
        description="Three or four answer options. Don't add an \"I'm not sure\" option; the "
        "app adds one."
    )
    correct_option: int | None = Field(
        description="Zero-based index of the correct option, or null for a self-assessment "
        "question with no right answer."
    )
    concept: str = Field(description="The concept or skill the question probes, in a few words.")


class DiagnosticQuizDraft(DraftModel):
    questions: list[DiagnosticQuestionDraft] = Field(description="Three or four questions.")


class DiagnosticQuestion(DiagnosticQuestionDraft):
    id: str


class DiagnosticAnswer(BaseModel):
    question_id: str
    option: int | None = None  # None means "I'm not sure"


# --- Learner profile and outline -------------------------------------------------------------


class LearnerProfile(DraftModel):
    level: Literal["beginner", "intermediate", "advanced"]
    summary: str = Field(
        description="One or two sentences on what the learner already knows and where to start."
    )
    strengths: list[str] = Field(description="Concepts the learner already seems comfortable with.")
    gaps: list[str] = Field(description="Concepts the course should build up carefully.")


class OutlineSectionDraft(DraftModel):
    title: str
    summary: str = Field(description="One sentence on what the section teaches.")


class OutlineModuleDraft(DraftModel):
    title: str
    summary: str = Field(description="One sentence on what the module covers.")
    sections: list[OutlineSectionDraft]


class OutlineDraft(DraftModel):
    title: str = Field(description="A short, specific course title.")
    description: str = Field(description="Two sentences describing the course for this learner.")
    modules: list[OutlineModuleDraft]


class CoursePlanDraft(DraftModel):
    profile: LearnerProfile
    title: str = Field(description="A short, specific course title.")
    description: str = Field(description="Two sentences describing the course for this learner.")
    modules: list[OutlineModuleDraft]


class OutlineSection(BaseModel):
    id: str
    title: str
    summary: str = ""


class OutlineModule(BaseModel):
    id: str
    title: str
    summary: str = ""
    sections: list[OutlineSection]


# --- Sections --------------------------------------------------------------------------------


class SectionDraft(DraftModel):
    blocks: list[BlockDraft]
    recap: str = Field(
        description="Two or three sentences summarising what this section taught. Later "
        "sections use it to stay consistent and avoid repetition."
    )


class ResearchSource(BaseModel):
    title: str
    url: str


class ResearchNotes(BaseModel):
    notes: str  # Markdown
    sources: list[ResearchSource] = []


# --- API -------------------------------------------------------------------------------------


class CourseCreate(BaseModel):
    goal: str = Field(min_length=3, max_length=500)
    depth: Depth = Depth.practitioner
    learning_style: LearningStyle = LearningStyle.reading
    background: str = Field(default="", max_length=1000)


class DiagnosticQuestionOut(BaseModel):
    id: str
    question: str
    options: list[str]
    concept: str


class DiagnosticAnswersIn(BaseModel):
    answers: list[DiagnosticAnswer] = []  # Empty when the learner skips the diagnostic


class OutlineSectionIn(BaseModel):
    id: str | None = None  # New sections have no id yet
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=600)


class OutlineModuleIn(BaseModel):
    id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=600)
    sections: list[OutlineSectionIn] = Field(min_length=1, max_length=20)


class OutlineUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    modules: list[OutlineModuleIn] = Field(min_length=1, max_length=20)


class OutlineRegenerate(BaseModel):
    instructions: str = Field(default="", max_length=1000)


class SectionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    summary: str
    position: int
    module_index: int
    status: SectionStatus
    stage: SectionStage | None
    completed_at: datetime | None


class CourseOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    goal: str
    depth: Depth
    learning_style: LearningStyle
    background: str
    status: CourseStatus
    error: str | None
    diagnostics: list[DiagnosticQuestionOut]
    profile: LearnerProfile | None
    outline: list[OutlineModule]
    sections: list[SectionSummary]
    current_section_id: uuid.UUID | None
    model: str
    created: datetime
    updated: datetime


class CourseListItem(BaseModel):
    id: uuid.UUID
    title: str
    goal: str
    depth: Depth
    learning_style: LearningStyle
    status: CourseStatus
    sections_total: int
    sections_completed: int
    current_section_id: uuid.UUID | None
    updated: datetime


class SectionOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    summary: str
    position: int
    module_index: int
    module_title: str
    status: SectionStatus
    stage: SectionStage | None
    blocks: list[Block]
    research: ResearchNotes | None
    error: str | None
    generated_at: datetime | None
    completed_at: datetime | None
    previous_section_id: uuid.UUID | None
    next_section_id: uuid.UUID | None

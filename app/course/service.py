"""The course lifecycle: diagnostic questions -> plan -> editable outline -> started course."""

import logging
import uuid

from sqlalchemy import func
from sqlmodel import col, delete, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.course.models import Course, Section
from app.course.schemas import (
    CourseCreate,
    CourseListItem,
    CourseOut,
    CoursePlanDraft,
    CourseStatus,
    Depth,
    DiagnosticAnswer,
    DiagnosticQuestion,
    DiagnosticQuestionOut,
    DiagnosticQuizDraft,
    OutlineDraft,
    OutlineModule,
    OutlineModuleDraft,
    OutlineSection,
    OutlineUpdate,
    SectionSummary,
)
from app.db.session import get_session
from app.errors import ConflictError, NotFoundError
from app.llm import LLMError, LLMRequest, Message, generate, get_llm
from app.llm.exceptions import LLMOutputError
from app.llm.prompts import render_prompt
from app.settings import settings
from app.tutor.models import Thread, ThreadMessage
from app.util import short_id

logger = logging.getLogger(__name__)

COURSE_SIZE = {
    Depth.overview: "three or four modules of two or three sections each",
    Depth.practitioner: "four or five modules of three or four sections each",
    Depth.rigorous: "five or six modules of three or four sections each",
}
MAX_DIAGNOSTIC_QUESTIONS = 4
NOT_SURE = "I'm not sure"


async def get_course(db: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await db.get(Course, course_id)
    if course is None:
        raise NotFoundError("Course not found.")
    return course


# --- Diagnostic ------------------------------------------------------------------------------


async def create_course(db: AsyncSession, data: CourseCreate) -> Course:
    """Create a course and write the diagnostic questions that gauge the learner's level."""
    system, user = render_prompt(
        "diagnostics",
        goal=data.goal,
        depth=data.depth,
        style=data.learning_style,
        background=data.background,
    )
    quiz = await generate(
        LLMRequest(
            task="diagnostics",
            system=system,
            messages=[Message("user", user)],
            effort=settings.EFFORT_DIAGNOSTICS,
            max_tokens=8_000,
            meta={"goal": data.goal, "depth": data.depth, "style": data.learning_style},
        ),
        DiagnosticQuizDraft,
    )
    course = Course(
        title=_provisional_title(data.goal),
        goal=data.goal,
        depth=data.depth,
        learning_style=data.learning_style,
        background=data.background,
        status=CourseStatus.diagnostic,
        diagnostics=[q.model_dump() for q in _clean_questions(quiz)],
        model=get_llm().model,
    )
    db.add(course)
    await db.commit()
    return course


def _provisional_title(goal: str) -> str:
    title = goal.strip().rstrip(".?!")
    return title[0].upper() + title[1:] if len(title) <= 80 else title[:77].rstrip() + "..."


def _clean_questions(quiz: DiagnosticQuizDraft) -> list[DiagnosticQuestion]:
    questions = []
    for draft in quiz.questions:
        options = [option.strip() for option in draft.options if option.strip()]
        if not draft.question.strip() or len(options) < 2:
            continue
        correct = draft.correct_option
        if correct is not None and not 0 <= correct < len(options):
            correct = None
        questions.append(
            DiagnosticQuestion(
                id=short_id("q"),
                question=draft.question.strip(),
                options=options,
                correct_option=correct,
                concept=draft.concept.strip(),
            )
        )
    return questions[:MAX_DIAGNOSTIC_QUESTIONS]


async def submit_answers(
    db: AsyncSession, course: Course, answers: list[DiagnosticAnswer]
) -> Course:
    """Store the learner's answers (none if they skipped) and move on to planning."""
    if course.status != CourseStatus.diagnostic:
        raise ConflictError("This course has already been planned.")
    questions = {q["id"]: q for q in course.diagnostics}
    cleaned = []
    for answer in answers:
        question = questions.get(answer.question_id)
        if question is None:
            continue
        option = answer.option
        if option is not None and not 0 <= option < len(question["options"]):
            option = None
        cleaned.append(DiagnosticAnswer(question_id=answer.question_id, option=option))
    course.answers = [answer.model_dump() for answer in cleaned]
    course.status = CourseStatus.planning
    course.error = None
    await db.commit()
    return course


# --- Planning ------------------------------------------------------------------------------


async def retry_planning(db: AsyncSession, course: Course) -> Course:
    if course.status != CourseStatus.planning_failed:
        raise ConflictError("Only a course whose planning failed can be retried.")
    course.status = CourseStatus.planning
    course.error = None
    await db.commit()
    return course


async def plan_course(course_id: uuid.UUID) -> None:
    """Background job: write the learner profile and the outline from the diagnostic answers."""
    async with get_session() as db:
        course = await db.get(Course, course_id)
        if course is None or course.status != CourseStatus.planning:
            return
        request = _plan_request(course)

    try:
        plan = await generate(request, CoursePlanDraft)
        outline = _outline_from_drafts(plan.modules)
        if not outline:
            raise LLMOutputError("The outline came back empty.")
    except Exception as e:
        if not isinstance(e, LLMError):
            logger.exception("Planning course %s failed", course_id)
        message = str(e) if isinstance(e, LLMError) else "Something went wrong planning the course."
        await _finish_planning(course_id, CourseStatus.planning_failed, error=message)
        return

    await _finish_planning(
        course_id,
        CourseStatus.outline_ready,
        profile=plan.profile.model_dump(),
        title=plan.title.strip(),
        description=plan.description.strip(),
        outline=outline,
    )


def _plan_request(course: Course) -> LLMRequest:
    answers = []
    by_question = {a["question_id"]: a for a in course.answers}
    for question in course.diagnostics:
        answer = by_question.get(question["id"])
        if answer is None:
            continue
        option, correct = answer["option"], question["correct_option"]
        answers.append(
            {
                "question": question["question"],
                "answer": question["options"][option] if option is not None else NOT_SURE,
                "correct_answer": question["options"][correct] if correct is not None else None,
                "is_correct": option is not None and option == correct,
            }
        )
    system, user = render_prompt(
        "plan",
        goal=course.goal,
        depth=course.depth,
        style=course.learning_style,
        background=course.background,
        sizing=COURSE_SIZE[Depth(course.depth)],
        answers=answers,
    )
    return LLMRequest(
        task="plan",
        system=system,
        messages=[Message("user", user)],
        effort=settings.EFFORT_PLAN,
        max_tokens=16_000,
        meta={
            "goal": course.goal,
            "depth": course.depth,
            "style": course.learning_style,
            "correct_answers": sum(a["is_correct"] for a in answers),
        },
    )


def _outline_from_drafts(modules: list[OutlineModuleDraft]) -> list[dict]:
    outline = []
    for module in modules:
        sections = [
            OutlineSection(id=str(uuid.uuid4()), title=s.title.strip(), summary=s.summary.strip())
            for s in module.sections
            if s.title.strip()
        ]
        if module.title.strip() and sections:
            outline.append(
                OutlineModule(
                    id=short_id("m"),
                    title=module.title.strip(),
                    summary=module.summary.strip(),
                    sections=sections,
                ).model_dump()
            )
    return outline


async def _finish_planning(
    course_id: uuid.UUID, status: CourseStatus, error: str | None = None, **values
) -> None:
    if not values.get("title"):
        values.pop("title", None)  # Keep the current title rather than blanking it
    async with get_session() as db:
        await db.exec(
            update(Course)
            .where(col(Course.id) == course_id, col(Course.status) == CourseStatus.planning)
            .values(status=status, error=error, **values)
        )
        await db.commit()


# --- Outline editing -------------------------------------------------------------------------


async def update_outline(db: AsyncSession, course: Course, data: OutlineUpdate) -> Course:
    """Save the learner's edits. New items get ids; section ids become the sections' ids."""
    if course.status != CourseStatus.outline_ready:
        raise ConflictError("The outline can only be edited before the course starts.")
    seen: set[str] = set()
    modules = []
    for module in data.modules:
        module_id = module.id if module.id and module.id not in seen else short_id("m")
        seen.add(module_id)
        sections = []
        for section in module.sections:
            section_id = section.id if _is_uuid(section.id) and section.id not in seen else None
            section_id = section_id or str(uuid.uuid4())
            seen.add(section_id)
            sections.append(
                OutlineSection(id=section_id, title=section.title, summary=section.summary)
            )
        modules.append(
            OutlineModule(
                id=module_id, title=module.title, summary=module.summary, sections=sections
            ).model_dump()
        )
    course.title = data.title
    course.description = data.description
    course.outline = modules
    course.error = None
    await db.commit()
    return course


def _is_uuid(value: str | None) -> bool:
    try:
        uuid.UUID(value or "")
    except ValueError:
        return False
    return True


async def request_outline_revision(db: AsyncSession, course: Course) -> Course:
    if course.status != CourseStatus.outline_ready:
        raise ConflictError("The outline can only be revised before the course starts.")
    course.status = CourseStatus.planning
    course.error = None
    await db.commit()
    return course


async def revise_outline(course_id: uuid.UUID, instructions: str) -> None:
    """Background job: rewrite the outline following the learner's instructions."""
    async with get_session() as db:
        course = await db.get(Course, course_id)
        if course is None or course.status != CourseStatus.planning:
            return
        system, user = render_prompt(
            "outline",
            goal=course.goal,
            depth=course.depth,
            style=course.learning_style,
            profile=course.profile,
            sizing=COURSE_SIZE[Depth(course.depth)],
            title=course.title,
            modules=course.outline,
            instructions=instructions,
        )
        request = LLMRequest(
            task="outline",
            system=system,
            messages=[Message("user", user)],
            effort=settings.EFFORT_PLAN,
            max_tokens=16_000,
            meta={
                "goal": course.goal,
                "depth": course.depth,
                "instructions": instructions,
                "current_title": course.title,
            },
        )

    try:
        draft = await generate(request, OutlineDraft, use_cache=False)
        outline = _outline_from_drafts(draft.modules)
        if not outline:
            raise LLMOutputError("The revised outline came back empty.")
    except Exception as e:
        if not isinstance(e, LLMError):
            logger.exception("Revising the outline of course %s failed", course_id)
        # The previous outline is still there, so go back to it and report the problem
        message = str(e) if isinstance(e, LLMError) else "Something went wrong."
        await _finish_planning(
            course_id, CourseStatus.outline_ready, error=f"Couldn't revise the outline. {message}"
        )
        return

    await _finish_planning(
        course_id,
        CourseStatus.outline_ready,
        title=draft.title.strip(),
        description=draft.description.strip(),
        outline=outline,
    )


# --- Starting, reading and deleting ----------------------------------------------------------


async def start_course(db: AsyncSession, course: Course) -> Course:
    """Turn the outline into sections. Nothing is written until a section is opened."""
    if course.status == CourseStatus.in_progress:
        return course
    if course.status != CourseStatus.outline_ready:
        raise ConflictError("The course isn't ready to start yet.")

    sections = []
    for module_index, module in enumerate(course.outline):
        for section in module["sections"]:
            sections.append(
                Section(
                    id=uuid.UUID(section["id"]),
                    course_id=course.id,
                    position=len(sections),
                    module_index=module_index,
                    module_title=module["title"],
                    title=section["title"],
                    summary=section["summary"],
                )
            )
    if not sections:
        raise ConflictError("Add at least one section to the outline first.")
    # Claim the transition so two simultaneous starts can't both create the sections
    result = await db.exec(
        update(Course)
        .where(col(Course.id) == course.id, col(Course.status) == CourseStatus.outline_ready)
        .values(status=CourseStatus.in_progress, current_section_id=sections[0].id)
    )
    if result.rowcount != 1:
        await db.rollback()
        raise ConflictError("The course was started already.")
    db.add_all(sections)
    await db.commit()
    await db.refresh(course)
    return course


async def course_out(db: AsyncSession, course: Course) -> CourseOut:
    sections = await db.exec(
        select(Section).where(Section.course_id == course.id).order_by(col(Section.position))
    )
    return CourseOut(
        id=course.id,
        title=course.title,
        description=course.description,
        goal=course.goal,
        depth=course.depth,
        learning_style=course.learning_style,
        background=course.background,
        status=course.status,
        error=course.error,
        diagnostics=[DiagnosticQuestionOut.model_validate(q) for q in course.diagnostics],
        profile=course.profile,
        outline=course.outline,
        sections=[SectionSummary.model_validate(s) for s in sections.all()],
        current_section_id=course.current_section_id,
        model=course.model,
        created=course.created,
        updated=course.updated,
    )


async def list_courses(db: AsyncSession) -> list[CourseListItem]:
    courses = (await db.exec(select(Course).order_by(col(Course.updated).desc()))).all()
    counts = await db.exec(
        select(Section.course_id, func.count(), func.count(col(Section.completed_at))).group_by(
            col(Section.course_id)
        )
    )
    progress = {course_id: (total, done) for course_id, total, done in counts.all()}
    return [
        CourseListItem(
            id=course.id,
            title=course.title,
            goal=course.goal,
            depth=course.depth,
            learning_style=course.learning_style,
            status=course.status,
            sections_total=progress.get(course.id, (0, 0))[0],
            sections_completed=progress.get(course.id, (0, 0))[1],
            current_section_id=course.current_section_id,
            updated=course.updated,
        )
        for course in courses
    ]


async def delete_course(db: AsyncSession, course: Course) -> None:
    # Delete children explicitly: SQLite (used in tests) doesn't enforce ON DELETE CASCADE
    thread_ids = select(Thread.id).where(Thread.course_id == course.id)
    await db.exec(delete(ThreadMessage).where(col(ThreadMessage.thread_id).in_(thread_ids)))
    await db.exec(delete(Thread).where(col(Thread.course_id) == course.id))
    await db.exec(delete(Section).where(col(Section.course_id) == course.id))
    await db.delete(course)
    await db.commit()

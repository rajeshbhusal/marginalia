import uuid

from fastapi import APIRouter, Response

from app import jobs
from app.course import generation, service
from app.course.schemas import (
    CourseCreate,
    CourseListItem,
    CourseOut,
    DiagnosticAnswersIn,
    OutlineRevision,
    OutlineUpdate,
    SectionGenerate,
    SectionOut,
    SectionProgress,
    SectionStatus,
)
from app.db.session import DBSession
from app.errors import ConflictError

router = APIRouter(prefix="/api", tags=["courses"])


@router.get("/courses")
async def list_courses(db: DBSession) -> list[CourseListItem]:
    return await service.list_courses(db)


@router.post("/courses", status_code=201)
async def create_course(data: CourseCreate, db: DBSession) -> CourseOut:
    """Start a course: writes the diagnostic questions (takes a few seconds)."""
    course = await service.create_course(db, data)
    return await service.course_out(db, course)


@router.get("/courses/{course_id}")
async def get_course(course_id: uuid.UUID, db: DBSession) -> CourseOut:
    course = await service.get_course(db, course_id)
    return await service.course_out(db, course)


@router.delete("/courses/{course_id}", status_code=204)
async def delete_course(course_id: uuid.UUID, db: DBSession) -> Response:
    course = await service.get_course(db, course_id)
    await service.delete_course(db, course)
    return Response(status_code=204)


@router.post("/courses/{course_id}/answers", status_code=202)
async def submit_answers(
    course_id: uuid.UUID, data: DiagnosticAnswersIn, db: DBSession
) -> CourseOut:
    """Submit the diagnostic answers (or none, to skip) and start planning in the background."""
    course = await service.get_course(db, course_id)
    course = await service.submit_answers(db, course, data.answers)
    jobs.spawn(service.plan_course(course.id))
    return await service.course_out(db, course)


@router.post("/courses/{course_id}/plan/retry", status_code=202)
async def retry_planning(course_id: uuid.UUID, db: DBSession) -> CourseOut:
    course = await service.get_course(db, course_id)
    course = await service.retry_planning(db, course)
    jobs.spawn(service.plan_course(course.id))
    return await service.course_out(db, course)


@router.put("/courses/{course_id}/outline")
async def update_outline(course_id: uuid.UUID, data: OutlineUpdate, db: DBSession) -> CourseOut:
    course = await service.get_course(db, course_id)
    course = await service.update_outline(db, course, data)
    return await service.course_out(db, course)


@router.post("/courses/{course_id}/outline/revise", status_code=202)
async def revise_outline(course_id: uuid.UUID, data: OutlineRevision, db: DBSession) -> CourseOut:
    """Ask the model to rework the outline, e.g. "more hands-on, skip the history"."""
    course = await service.get_course(db, course_id)
    course = await service.request_outline_revision(db, course)
    jobs.spawn(service.revise_outline(course.id, data.instructions))
    return await service.course_out(db, course)


@router.post("/courses/{course_id}/start")
async def start_course(course_id: uuid.UUID, db: DBSession) -> CourseOut:
    course = await service.get_course(db, course_id)
    course = await service.start_course(db, course)
    if course.current_section_id:
        jobs.spawn(generation.generate_section(course.current_section_id))
    return await service.course_out(db, course)


@router.get("/sections/{section_id}")
async def get_section(section_id: uuid.UUID, db: DBSession) -> SectionOut:
    section = await generation.get_section(db, section_id)
    return await generation.section_out(db, section)


@router.post("/sections/{section_id}/open")
async def open_section(section_id: uuid.UUID, db: DBSession) -> SectionOut:
    """The learner opened this section: write it now if needed, and prefetch the next one."""
    section = await generation.get_section(db, section_id)
    for wanted in await generation.open_section(db, section):
        jobs.spawn(generation.generate_section(wanted))
    await db.refresh(section)
    return await generation.section_out(db, section)


@router.post("/sections/{section_id}/generate", status_code=202)
async def generate_section(
    section_id: uuid.UUID, data: SectionGenerate, db: DBSession
) -> SectionOut:
    """Retry a failed or stuck section, or rewrite a finished one with `regenerate`."""
    section = await generation.get_section(db, section_id)
    if section.status == SectionStatus.ready:
        if not data.regenerate:
            raise ConflictError("This section is already written. Pass regenerate to rewrite it.")
        await generation.prepare_regeneration(db, section)
    elif section.status == SectionStatus.generating and not generation.is_stale(section):
        raise ConflictError("This section is being written right now.")
    jobs.spawn(generation.generate_section(section.id, force=data.regenerate))
    return await generation.section_out(db, section)


@router.put("/sections/{section_id}/progress")
async def set_progress(section_id: uuid.UUID, data: SectionProgress, db: DBSession) -> SectionOut:
    section = await generation.get_section(db, section_id)
    section = await generation.set_completed(db, section, data.completed)
    return await generation.section_out(db, section)

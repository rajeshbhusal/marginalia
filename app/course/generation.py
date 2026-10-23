"""Writes sections just in time: research notes first, then the lesson, streamed into the DB.

A section is generated when the learner opens it (and the next one is prefetched), never in
advance for the whole course. Progress lives on the section row, so any API process can report
it and a job lost to a restart can be claimed again once it's stale.
"""

import logging
import time
import uuid
from datetime import timedelta

from pydantic import ValidationError
from pydantic_core import from_json
from sqlmodel import col, delete, or_, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.course.blocks import block_draft_adapter, new_block_id, with_id
from app.course.models import Course, Section
from app.course.schemas import (
    Depth,
    ResearchNotes,
    ResearchSource,
    SectionDraft,
    SectionOut,
    SectionStage,
    SectionStatus,
)
from app.db.base_model import get_utc_now
from app.db.session import get_session
from app.errors import NotFoundError
from app.llm import LLMError, LLMRequest, Message, generate, get_llm, research
from app.llm.exceptions import LLMOutputError
from app.llm.prompts import render_prompt
from app.settings import settings
from app.tutor.models import Thread, ThreadMessage

logger = logging.getLogger(__name__)

SECTION_LENGTH = {
    Depth.overview: "500 to 800",
    Depth.practitioner: "900 to 1,400",
    Depth.rigorous: "1,300 to 2,000",
}


async def get_section(db: AsyncSession, section_id: uuid.UUID) -> Section:
    section = await db.get(Section, section_id)
    if section is None:
        raise NotFoundError("Section not found.")
    return section


def is_stale(section: Section) -> bool:
    if section.status != SectionStatus.generating or section.generation_started_at is None:
        return False
    age = get_utc_now() - section.generation_started_at
    return age > timedelta(seconds=settings.GENERATION_STALE_AFTER_SECONDS)


async def claim_section(section_id: uuid.UUID, *, force: bool = False) -> bool:
    """Atomically mark a section as generating. Only one caller can win the claim."""
    now = get_utc_now()
    stale_before = now - timedelta(seconds=settings.GENERATION_STALE_AFTER_SECONDS)
    claimable = or_(
        col(Section.status).in_([SectionStatus.pending, SectionStatus.failed]),
        (col(Section.status) == SectionStatus.generating)
        & (col(Section.generation_started_at) < stale_before),
    )
    if force:
        claimable = or_(claimable, col(Section.status) == SectionStatus.ready)
    async with get_session() as db:
        result = await db.exec(
            update(Section)
            .where(col(Section.id) == section_id, claimable)
            .values(
                status=SectionStatus.generating,
                stage=SectionStage.queued,
                generation_started_at=now,
                blocks=[],
                error=None,
            )
        )
        await db.commit()
    return result.rowcount == 1


async def generate_section(section_id: uuid.UUID, *, force: bool = False) -> None:
    """Background job: research and write one section, unless someone else already is."""
    if not await claim_section(section_id, force=force):
        return
    try:
        await _write_section(section_id, use_cache=not force)
    except Exception as e:
        if not isinstance(e, LLMError):
            logger.exception("Writing section %s failed", section_id)
        message = (
            str(e) if isinstance(e, LLMError) else "Something went wrong writing this section."
        )
        await _update_generating(section_id, status=SectionStatus.failed, stage=None, error=message)


async def _write_section(section_id: uuid.UUID, use_cache: bool) -> None:
    async with get_session() as db:
        section = await db.get(Section, section_id)
        course = await db.get(Course, section.course_id) if section else None
        if section is None or course is None:
            return  # Deleted while queued
        earlier = await db.exec(
            select(Section)
            .where(
                Section.course_id == course.id,
                Section.position < section.position,
                Section.status == SectionStatus.ready,
            )
            .order_by(col(Section.position))
        )
        recaps = [{"title": s.title, "recap": s.recap} for s in earlier.all() if s.recap]

    notes = None
    if settings.RESEARCH_BACKEND == "web":
        notes = await _research(course, section)

    await _update_generating(
        section_id,
        stage=SectionStage.writing,
        research=notes.model_dump() if notes else None,
    )
    system, user = render_prompt(
        "section",
        depth=course.depth,
        style=course.learning_style,
        profile=course.profile,
        length=SECTION_LENGTH[Depth(course.depth)],
        course_title=course.title,
        course_description=course.description,
        goal=course.goal,
        outline=course.outline,
        section_id=str(section.id),
        recaps=recaps,
        research_notes=notes.notes if notes else "",
        section_title=section.title,
        section_summary=section.summary,
    )
    writer = PartialSectionWriter(section_id)
    draft = await generate(
        LLMRequest(
            task="section",
            system=system,
            messages=[Message("user", user)],
            effort=settings.EFFORT_SECTION,
            max_tokens=32_000,
            meta={
                "course_title": course.title,
                "module_title": section.module_title,
                "section_title": section.title,
                "section_summary": section.summary,
                "style": course.learning_style,
                "depth": course.depth,
            },
        ),
        SectionDraft,
        on_partial=writer.on_partial,
        use_cache=use_cache,
    )
    blocks = [
        with_id(block, writer.block_id(i)).model_dump() for i, block in enumerate(draft.blocks)
    ]
    if not blocks:
        raise LLMOutputError("The section came back empty.")

    await _update_generating(
        section_id,
        status=SectionStatus.ready,
        stage=None,
        blocks=blocks,
        recap=draft.recap.strip(),
        generated_at=get_utc_now(),
        model=get_llm().model,
        error=None,
    )


async def _research(course: Course, section: Section) -> ResearchNotes | None:
    await _update_generating(section.id, stage=SectionStage.researching)
    system, user = render_prompt(
        "research",
        course_title=course.title,
        goal=course.goal,
        module_title=section.module_title,
        section_title=section.title,
        section_summary=section.summary,
    )
    request = LLMRequest(
        task="research",
        system=system,
        messages=[Message("user", user)],
        effort=settings.EFFORT_RESEARCH,
        max_tokens=16_000,
        meta={"course_title": course.title, "section_title": section.title},
    )
    try:
        result = await research(request, settings.RESEARCH_MAX_SEARCHES)
    except LLMError as e:
        # Notes improve accuracy but aren't essential, so write the section without them
        logger.warning("Research for section %s failed, writing without notes: %s", section.id, e)
        return None
    if result is None or not result.notes:
        return None
    return ResearchNotes(
        notes=result.notes,
        sources=[ResearchSource(title=s.title, url=s.url) for s in result.sources],
    )


async def _update_generating(section_id: uuid.UUID, **values) -> None:
    """Update a section that is still being generated (so a reset section isn't overwritten)."""
    async with get_session() as db:
        await db.exec(
            update(Section)
            .where(col(Section.id) == section_id, col(Section.status) == SectionStatus.generating)
            .values(**values)
        )
        await db.commit()


class PartialSectionWriter:
    """Saves each block as soon as it has fully streamed in, so the reader can show it early."""

    parse_interval = 0.4  # Seconds between parses of the growing response

    def __init__(self, section_id: uuid.UUID):
        self.section_id = section_id
        self.ids: list[str] = []
        self.saved = 0
        self._last_parse = 0.0

    def block_id(self, index: int) -> str:
        # Partial saves and the final save use the same ids, so blocks keep their identity
        while len(self.ids) <= index:
            self.ids.append(new_block_id())
        return self.ids[index]

    def complete_blocks(self, text: str) -> list[dict]:
        try:
            data = from_json(text, allow_partial=True)
        except ValueError:
            return []
        if not isinstance(data, dict) or not isinstance(data.get("blocks"), list):
            return []
        items = data["blocks"]
        if "recap" not in data:
            items = items[:-1]  # The last block may still be streaming until the list closes
        blocks = []
        for index, item in enumerate(items):
            try:
                draft = block_draft_adapter.validate_python(item)
            except ValidationError:
                break
            blocks.append(with_id(draft, self.block_id(index)).model_dump())
        return blocks

    async def on_partial(self, text: str) -> None:
        now = time.monotonic()
        if now - self._last_parse < self.parse_interval:
            return
        self._last_parse = now
        blocks = self.complete_blocks(text)
        if len(blocks) > self.saved:
            self.saved = len(blocks)
            await _update_generating(self.section_id, blocks=blocks)


# --- Reading ---------------------------------------------------------------------------------


async def open_section(db: AsyncSession, section: Section) -> list[uuid.UUID]:
    """Make this the learner's current section; return the sections that should be written now.

    That's this section if it hasn't been written, plus the next one so it's ready in time.
    """
    course = await db.get(Course, section.course_id)
    course.current_section_id = section.id
    course.updated = get_utc_now()
    await db.commit()

    wanted = [section]
    if settings.PREFETCH_NEXT_SECTION:
        following = await db.exec(
            select(Section).where(
                Section.course_id == section.course_id, Section.position == section.position + 1
            )
        )
        wanted.extend(following.all())
    return [s.id for s in wanted if s.status == SectionStatus.pending or is_stale(s)]


async def prepare_regeneration(db: AsyncSession, section: Section) -> None:
    """Rewriting a section changes its blocks, so remove the threads anchored to the old ones."""
    thread_ids = select(Thread.id).where(Thread.section_id == section.id)
    await db.exec(delete(ThreadMessage).where(col(ThreadMessage.thread_id).in_(thread_ids)))
    await db.exec(delete(Thread).where(col(Thread.section_id) == section.id))
    await db.commit()


async def set_completed(db: AsyncSession, section: Section, completed: bool) -> Section:
    section.completed_at = get_utc_now() if completed else None
    await db.commit()
    return section


async def section_out(db: AsyncSession, section: Section) -> SectionOut:
    neighbours = await db.exec(
        select(Section.id, Section.position).where(
            Section.course_id == section.course_id,
            col(Section.position).in_([section.position - 1, section.position + 1]),
        )
    )
    by_position = {position: section_id for section_id, position in neighbours.all()}
    return SectionOut(
        id=section.id,
        course_id=section.course_id,
        title=section.title,
        summary=section.summary,
        position=section.position,
        module_index=section.module_index,
        module_title=section.module_title,
        status=section.status,
        stage=section.stage,
        blocks=section.blocks,
        research=section.research,
        error=section.error,
        generated_at=section.generated_at,
        completed_at=section.completed_at,
        previous_section_id=by_position.get(section.position - 1),
        next_section_id=by_position.get(section.position + 1),
    )

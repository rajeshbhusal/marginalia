"""Highlight-and-ask: answers questions about a passage, in a thread anchored next to it."""

import uuid

from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.course.blocks import Block, block_adapter, render_block_markdown
from app.course.models import Course, Section
from app.course.schemas import SectionStatus
from app.db.base_model import get_utc_now
from app.errors import ConflictError, NotFoundError
from app.llm import LLMRequest, Message, generate_text
from app.llm.prompts import render_prompt
from app.settings import settings
from app.tutor.models import Thread, ThreadMessage
from app.tutor.schemas import MessageOut, ThreadCreate, ThreadOut

NEIGHBOUR_RADIUS = 2  # Blocks either side of the highlighted one, shown to the tutor up close


async def get_thread(db: AsyncSession, thread_id: uuid.UUID) -> Thread:
    thread = await db.get(Thread, thread_id)
    if thread is None:
        raise NotFoundError("Thread not found.")
    return thread


async def list_threads(db: AsyncSession, section_id: uuid.UUID) -> list[ThreadOut]:
    threads = await db.exec(
        select(Thread).where(Thread.section_id == section_id).order_by(col(Thread.created))
    )
    return [await thread_out(db, thread) for thread in threads.all()]


async def create_thread(db: AsyncSession, section: Section, data: ThreadCreate) -> ThreadOut:
    """Ask about a highlighted passage. Nothing is saved unless the tutor answers."""
    blocks = _ready_blocks(section)
    if not any(block.id == data.block_id for block in blocks):
        raise NotFoundError("The highlighted passage isn't part of this section.")
    asked = ThreadMessage(thread_id=uuid.uuid4(), role="learner", content=data.question)
    thread = Thread(
        id=asked.thread_id,
        course_id=section.course_id,
        section_id=section.id,
        block_id=data.block_id,
        quote=data.quote,
        prefix=data.prefix,
        suffix=data.suffix,
    )
    request = await _tutor_request(db, section, blocks, thread, history=[asked])
    await db.commit()  # Release the connection while the model answers
    answer = await generate_text(request)

    db.add(thread)
    db.add(asked)
    db.add(ThreadMessage(thread_id=thread.id, role="tutor", content=answer))
    await db.commit()
    return await thread_out(db, thread)


async def add_message(db: AsyncSession, thread: Thread, content: str) -> ThreadOut:
    """Ask a follow-up question in an existing thread."""
    section = await db.get(Section, thread.section_id)
    blocks = _ready_blocks(section)
    history = list(await _messages(db, thread.id))
    asked = ThreadMessage(thread_id=thread.id, role="learner", content=content)
    request = await _tutor_request(db, section, blocks, thread, history=[*history, asked])
    await db.commit()
    answer = await generate_text(request)

    db.add(asked)
    db.add(ThreadMessage(thread_id=thread.id, role="tutor", content=answer))
    thread.resolved = False
    thread.updated = get_utc_now()
    await db.commit()
    return await thread_out(db, thread)


async def set_resolved(db: AsyncSession, thread: Thread, resolved: bool) -> ThreadOut:
    thread.resolved = resolved
    await db.commit()
    return await thread_out(db, thread)


async def delete_thread(db: AsyncSession, thread: Thread) -> None:
    await db.exec(delete(ThreadMessage).where(col(ThreadMessage.thread_id) == thread.id))
    await db.delete(thread)
    await db.commit()


async def thread_out(db: AsyncSession, thread: Thread) -> ThreadOut:
    return ThreadOut(
        id=thread.id,
        section_id=thread.section_id,
        block_id=thread.block_id,
        quote=thread.quote,
        prefix=thread.prefix,
        suffix=thread.suffix,
        resolved=thread.resolved,
        created=thread.created,
        messages=[MessageOut.model_validate(m) for m in await _messages(db, thread.id)],
    )


async def _messages(db: AsyncSession, thread_id: uuid.UUID):
    messages = await db.exec(
        select(ThreadMessage)
        .where(ThreadMessage.thread_id == thread_id)
        # "learner" sorts before "tutor" if two messages share a timestamp
        .order_by(col(ThreadMessage.created), col(ThreadMessage.role))
    )
    return messages.all()


def _ready_blocks(section: Section | None) -> list[Block]:
    if section is None:
        raise NotFoundError("Section not found.")
    if section.status != SectionStatus.ready:
        raise ConflictError("You can ask about a section once it has been written.")
    return [block_adapter.validate_python(block) for block in section.blocks]


async def _tutor_request(
    db: AsyncSession,
    section: Section,
    blocks: list[Block],
    thread: Thread,
    history: list[ThreadMessage],
) -> LLMRequest:
    """Build the tutor's request: the section as a cacheable system prompt, then the thread."""
    course = await db.get(Course, section.course_id)
    titles = await db.exec(
        select(Section.position, Section.title)
        .where(Section.course_id == course.id)
        .order_by(col(Section.position))
    )
    titles_by_position = dict(titles.all())
    research = section.research or {}

    system, first_question = render_prompt(
        "tutor",
        course_title=course.title,
        goal=course.goal,
        depth=course.depth,
        style=course.learning_style,
        profile=course.profile,
        module_title=section.module_title,
        position=section.position + 1,
        total_sections=len(titles_by_position),
        section_title=section.title,
        previous_title=titles_by_position.get(section.position - 1, ""),
        next_title=titles_by_position.get(section.position + 1, ""),
        blocks=[{"id": b.id, "type": b.type, "markdown": render_block_markdown(b)} for b in blocks],
        research_notes=research.get("notes", ""),
        block_id=thread.block_id,
        quote=thread.quote,
        block_markdown=_block_markdown(blocks, thread.block_id),
        neighbours=_neighbours(blocks, thread.block_id),
        question=history[0].content,
    )
    # The first learner turn carries the passage and its surroundings; later turns are plain
    messages = [Message("user", first_question)]
    messages += [
        Message("user" if m.role == "learner" else "assistant", m.content) for m in history[1:]
    ]
    return LLMRequest(
        task="tutor",
        system=system,
        messages=messages,
        effort=settings.EFFORT_TUTOR,
        max_tokens=8_000,
        cache_system=True,  # Every question about this section shares the system prompt
        meta={
            "quote": thread.quote,
            "question": history[-1].content,
            "style": course.learning_style,
            "section_title": section.title,
        },
    )


def _block_markdown(blocks: list[Block], block_id: str) -> str:
    for block in blocks:
        if block.id == block_id:
            return render_block_markdown(block)
    return "(This block is no longer in the section.)"


def _neighbours(blocks: list[Block], block_id: str) -> list[dict]:
    index = next((i for i, b in enumerate(blocks) if b.id == block_id), None)
    if index is None:
        return []
    start, end = max(0, index - NEIGHBOUR_RADIUS), min(len(blocks), index + NEIGHBOUR_RADIUS + 1)
    return [
        {
            "id": blocks[i].id,
            "relation": "before" if i < index else "after",
            "markdown": render_block_markdown(blocks[i]),
        }
        for i in range(start, end)
        if i != index
    ]

import uuid

from fastapi import APIRouter, Response

from app.course.generation import get_section
from app.db.session import DBSession
from app.tutor import service
from app.tutor.schemas import MessageCreate, ThreadCreate, ThreadOut, ThreadUpdate

router = APIRouter(prefix="/api", tags=["tutor"])


@router.get("/sections/{section_id}/threads")
async def list_threads(section_id: uuid.UUID, db: DBSession) -> list[ThreadOut]:
    await get_section(db, section_id)
    return await service.list_threads(db, section_id)


@router.post("/sections/{section_id}/threads", status_code=201)
async def create_thread(section_id: uuid.UUID, data: ThreadCreate, db: DBSession) -> ThreadOut:
    """Highlight-and-ask: start a margin thread on a passage and get the tutor's answer."""
    section = await get_section(db, section_id)
    return await service.create_thread(db, section, data)


@router.post("/threads/{thread_id}/messages")
async def add_message(thread_id: uuid.UUID, data: MessageCreate, db: DBSession) -> ThreadOut:
    thread = await service.get_thread(db, thread_id)
    return await service.add_message(db, thread, data.content)


@router.patch("/threads/{thread_id}")
async def update_thread(thread_id: uuid.UUID, data: ThreadUpdate, db: DBSession) -> ThreadOut:
    thread = await service.get_thread(db, thread_id)
    return await service.set_resolved(db, thread, data.resolved)


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: uuid.UUID, db: DBSession) -> Response:
    thread = await service.get_thread(db, thread_id)
    await service.delete_thread(db, thread)
    return Response(status_code=204)

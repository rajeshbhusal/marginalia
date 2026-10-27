"""Background jobs that run in the API process, such as writing a section.

Jobs record their progress in the database, so a job lost to a restart shows up as a stale
"generating" section that can simply be claimed again.
"""

import asyncio
import logging
from collections.abc import Coroutine

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()


def spawn(coro: Coroutine) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _tasks.add(task)  # Keep a reference so the task isn't garbage collected mid-run
    task.add_done_callback(_finished)
    return task


def _finished(task: asyncio.Task) -> None:
    _tasks.discard(task)
    if not task.cancelled() and task.exception() is not None:
        logger.error("Background job failed", exc_info=task.exception())


async def drain() -> None:
    """Wait for every running job, including jobs they start (used by tests and the CLI)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def cancel_all() -> None:
    for task in list(_tasks):
        task.cancel()
    await asyncio.gather(*list(_tasks), return_exceptions=True)

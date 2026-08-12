import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

log = logging.getLogger(__name__)


class TaskQueue(Protocol):
    """Boundary for async work dispatch (ADR-0001: Celery-swappable)."""

    def spawn(self, factory: Callable[[], Awaitable[None]]) -> None: ...


class BackgroundTaskQueue:
    """In-process asyncio tasks. Strong refs held until completion so tasks are never GC'd."""

    def __init__(self):
        self._tasks: set[asyncio.Task] = set()

    def spawn(self, factory: Callable[[], Awaitable[None]]) -> None:
        task = asyncio.create_task(self._run(factory))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @staticmethod
    async def _run(factory: Callable[[], Awaitable[None]]) -> None:
        try:
            await factory()
        except Exception:
            log.exception("background task failed")


class EagerTaskQueue:
    """Test double: runs the work inline at spawn-await point via a drain() call."""

    def __init__(self):
        self.pending: list[Callable[[], Awaitable[None]]] = []

    def spawn(self, factory: Callable[[], Awaitable[None]]) -> None:
        self.pending.append(factory)

    async def drain(self) -> None:
        while self.pending:
            await self.pending.pop(0)()

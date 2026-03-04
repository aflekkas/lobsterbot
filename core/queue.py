import asyncio
import fcntl
import logging
from pathlib import Path
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class ProcessLock:
    """File-based lock to coordinate bot and scheduler processes."""

    def __init__(self, lock_path: Path):
        self._path = lock_path
        self._file = None

    async def acquire(self):
        loop = asyncio.get_event_loop()
        self._file = open(self._path, "w")
        await loop.run_in_executor(None, self._lock)

    def _lock(self):
        fcntl.flock(self._file.fileno(), fcntl.LOCK_EX)

    def release(self):
        if self._file:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()
            self._file = None

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()


class ChatQueue:
    """Per-chat message queue that concatenates messages arriving while processing."""

    def __init__(self):
        self._pending: list[str] = []
        self._processing = False
        self._lock = asyncio.Lock()
        self._event = asyncio.Event()

    async def add(self, message: str):
        async with self._lock:
            self._pending.append(message)
            self._event.set()

    async def get_batch(self) -> str | None:
        async with self._lock:
            if not self._pending:
                return None
            batch = "\n\n".join(self._pending)
            self._pending.clear()
            self._event.clear()
            return batch

    @property
    def is_processing(self) -> bool:
        return self._processing

    @is_processing.setter
    def is_processing(self, value: bool):
        self._processing = value


class MessageRouter:
    """Routes messages through per-chat queues, ensuring sequential processing."""

    def __init__(self, process_lock: ProcessLock | None = None):
        self._queues: dict[int, ChatQueue] = {}
        self._process_lock = process_lock
        self._tasks: dict[int, asyncio.Task] = {}

    def _get_queue(self, chat_id: int) -> ChatQueue:
        if chat_id not in self._queues:
            self._queues[chat_id] = ChatQueue()
        return self._queues[chat_id]

    async def enqueue(
        self,
        chat_id: int,
        message: str,
        handler: Callable[[int, str], Awaitable[None]],
    ):
        queue = self._get_queue(chat_id)
        await queue.add(message)

        if not queue.is_processing:
            queue.is_processing = True
            self._tasks[chat_id] = asyncio.create_task(
                self._process_queue(chat_id, queue, handler)
            )

    async def _process_queue(
        self,
        chat_id: int,
        queue: ChatQueue,
        handler: Callable[[int, str], Awaitable[None]],
    ):
        try:
            while True:
                batch = await queue.get_batch()
                if batch is None:
                    break

                if self._process_lock:
                    async with self._process_lock:
                        await handler(chat_id, batch)
                else:
                    await handler(chat_id, batch)

                # Small delay to allow more messages to accumulate
                await asyncio.sleep(0.1)
        except Exception:
            logger.exception("Error processing queue for chat %s", chat_id)
        finally:
            queue.is_processing = False
            self._tasks.pop(chat_id, None)

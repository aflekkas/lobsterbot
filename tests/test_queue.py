import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from core.queue import ChatQueue, MessageRouter, ProcessLock


@pytest.mark.asyncio
async def test_chat_queue_single_message():
    q = ChatQueue()
    await q.add("hello")
    batch = await q.get_batch()
    assert batch == "hello"


@pytest.mark.asyncio
async def test_chat_queue_concatenates_messages():
    q = ChatQueue()
    await q.add("hello")
    await q.add("world")
    batch = await q.get_batch()
    assert batch == "hello\n\nworld"


@pytest.mark.asyncio
async def test_chat_queue_empty_returns_none():
    q = ChatQueue()
    batch = await q.get_batch()
    assert batch is None


@pytest.mark.asyncio
async def test_chat_queue_clears_after_get():
    q = ChatQueue()
    await q.add("hello")
    await q.get_batch()
    batch = await q.get_batch()
    assert batch is None


@pytest.mark.asyncio
async def test_router_processes_message():
    handler = AsyncMock()
    router = MessageRouter()
    await router.enqueue(123, "hello", handler)
    await asyncio.sleep(0.2)
    handler.assert_called_once_with(123, "hello")


@pytest.mark.asyncio
async def test_router_concatenates_during_processing():
    call_count = 0
    received_messages = []

    async def slow_handler(chat_id, message):
        nonlocal call_count
        call_count += 1
        received_messages.append(message)
        await asyncio.sleep(0.3)

    router = MessageRouter()
    await router.enqueue(123, "first", slow_handler)
    await asyncio.sleep(0.05)
    await router.enqueue(123, "second", slow_handler)
    await router.enqueue(123, "third", slow_handler)
    await asyncio.sleep(0.8)

    assert "first" in received_messages
    assert any("second" in m and "third" in m for m in received_messages)


@pytest.mark.asyncio
async def test_router_independent_chats():
    handler = AsyncMock()
    router = MessageRouter()
    await router.enqueue(111, "chat1", handler)
    await router.enqueue(222, "chat2", handler)
    await asyncio.sleep(0.3)
    assert handler.call_count == 2


@pytest.mark.asyncio
async def test_process_lock(tmp_path):
    lock = ProcessLock(tmp_path / "test.lock")
    async with lock:
        assert lock._file is not None
    assert lock._file is None

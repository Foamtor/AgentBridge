"""In-process lock / cancel adapter tests."""

import asyncio

import pytest
from agentbridge_core.adapters.inprocess_cancel import InProcessCancelRegistry
from agentbridge_core.adapters.inprocess_lock import InProcessThreadLock


@pytest.mark.asyncio
async def test_lock_busy():
    lock = InProcessThreadLock()
    assert await lock.try_acquire("t1", "r1") is True
    assert await lock.try_acquire("t1", "r2") is False
    await lock.release("t1", "r1")
    assert await lock.try_acquire("t1", "r3") is True


@pytest.mark.asyncio
async def test_cancel_registry():
    reg = InProcessCancelRegistry()
    token = asyncio.Event()
    await reg.register("t1", "r1", token)
    assert await reg.request_cancel("t1", "r1") is True
    assert token.is_set()
    await reg.unregister("t1", "r1")
    assert await reg.request_cancel("t1", "r1") is False


@pytest.mark.asyncio
async def test_cancel_rejects_non_event_token():
    reg = InProcessCancelRegistry()
    with pytest.raises(TypeError):
        await reg.register("t1", "r1", object())  # type: ignore[arg-type]

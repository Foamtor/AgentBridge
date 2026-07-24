"""Redis lock dual-acquire tests (FakeRedis)."""

from __future__ import annotations

import pytest
from adapters.redis_thread_lock import RedisThreadLock
from testing.fake_redis import FakeRedis


@pytest.mark.asyncio
async def test_redis_lock_second_acquire_fails() -> None:
    r = FakeRedis()
    lock = RedisThreadLock(r, ttl_seconds=30)
    key = "acme::thread-1"
    assert await lock.try_acquire(key, "r1") is True
    assert await lock.try_acquire(key, "r2") is False
    await lock.release(key, "r1")
    assert await lock.try_acquire(key, "r2") is True

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
    assert f"ab:lock:{key}" in r._kv
    assert await lock.try_acquire(key, "r2") is False
    await lock.release(key, "r1")
    assert f"ab:lock:{key}" not in r._kv
    assert await lock.try_acquire(key, "r2") is True


@pytest.mark.asyncio
async def test_two_lock_instances_share_redis_mutex() -> None:
    """Simulates two API processes sharing one Redis (M9 dual-instance mutex)."""
    r = FakeRedis()
    a = RedisThreadLock(r, ttl_seconds=30)
    b = RedisThreadLock(r, ttl_seconds=30)
    key = "acme::shared-thread"
    assert await a.try_acquire(key, "run-a") is True
    assert await b.try_acquire(key, "run-b") is False
    await a.release(key, "run-a")
    assert await b.try_acquire(key, "run-b") is True

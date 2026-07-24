"""Redis-backed ThreadLock — key ab:lock:{storage_key} (no extra tenant prefix)."""

from __future__ import annotations

from typing import Any


_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class RedisThreadLock:
    def __init__(self, redis: Any, *, ttl_seconds: int = 300) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def _key(self, storage_key: str) -> str:
        return f"ab:lock:{storage_key}"

    async def try_acquire(self, thread_id: str, run_id: str) -> bool:
        # thread_id argument is storage_key from lifecycle.
        ok = await self._redis.set(
            self._key(thread_id), run_id, nx=True, ex=self._ttl
        )
        return bool(ok)

    async def release(self, thread_id: str, run_id: str) -> None:
        await self._redis.eval(_RELEASE_LUA, 1, self._key(thread_id), run_id)

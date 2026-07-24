"""Minimal async Redis stand-in for unit tests (no redis package required)."""

from __future__ import annotations


class FakeRedis:
    def __init__(self) -> None:
        self._kv: dict[str, str | int] = {}

    async def set(
        self, key: str, value: str, nx: bool = False, ex: int | None = None
    ) -> bool:
        _ = ex
        if nx and key in self._kv:
            return False
        self._kv[key] = value
        return True

    async def incr(self, key: str) -> int:
        self._kv[key] = int(self._kv.get(key, 0)) + 1
        return int(self._kv[key])

    async def expire(self, key: str, seconds: int) -> bool:
        _ = (key, seconds)
        return True

    async def eval(self, script: str, numkeys: int, *args: str) -> int:
        _ = (script, numkeys)
        key, run_id = args[0], args[1]
        if self._kv.get(key) == run_id:
            del self._kv[key]
            return 1
        return 0

    async def aclose(self) -> None:
        self._kv.clear()

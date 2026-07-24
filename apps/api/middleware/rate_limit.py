"""In-process and Redis rate limiters."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

_INCR_EXPIRE_LUA = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return c
"""


class SlidingWindowLimiter:
    """Allow at most ``limit`` hits per ``window_seconds`` per key (in-process)."""

    def __init__(self, *, limit: int, window_seconds: float = 60.0) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, now: float | None = None) -> bool:
        if self._limit <= 0:
            return True
        t = time.monotonic() if now is None else now
        q = self._hits[key]
        cutoff = t - self._window
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= self._limit:
            return False
        q.append(t)
        return True


class RedisSlidingWindowLimiter:
    """Per-key counter with TTL window (INCR+EXPIRE via Lua, atomic)."""

    def __init__(
        self, redis: Any, *, limit: int, window_seconds: int = 60
    ) -> None:
        self._redis = redis
        self._limit = limit
        self._window = window_seconds

    async def allow(self, key: str) -> bool:
        if self._limit <= 0:
            return True
        rkey = f"ab:rl:{key}"
        count = await self._redis.eval(
            _INCR_EXPIRE_LUA, 1, rkey, str(self._window)
        )
        return int(count) <= self._limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-process limiter by default; Redis when ``redis`` is provided."""

    def __init__(
        self,
        app,
        *,
        limit_per_minute: int,
        redis: Any | None = None,
    ) -> None:
        super().__init__(app)
        self._limit = limit_per_minute
        self._sync = SlidingWindowLimiter(limit=limit_per_minute)
        self._async = (
            RedisSlidingWindowLimiter(redis, limit=limit_per_minute)
            if redis is not None and limit_per_minute > 0
            else None
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._limit <= 0:
            return await call_next(request)
        path = request.url.path
        if path in {"/health", "/ready", "/metrics"} or path.startswith(
            ("/docs", "/openapi")
        ):
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        try:
            if self._async is not None:
                allowed = await self._async.allow(client)
            else:
                allowed = self._sync.allow(client)
        except Exception:  # noqa: BLE001 — Redis/backend failure
            logger.exception("rate limit backend error")
            return JSONResponse(
                status_code=503,
                content={
                    "detail": {
                        "code": "rate_limit_unavailable",
                        "message": "rate limit backend unavailable",
                    }
                },
            )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": "rate_limited",
                        "message": "rate limit exceeded",
                    }
                },
            )
        return await call_next(request)

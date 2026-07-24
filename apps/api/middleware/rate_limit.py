"""In-process sliding-window rate limiter (single-node only)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SlidingWindowLimiter:
    """Allow at most ``limit`` hits per ``window_seconds`` per key."""

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


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limit_per_minute: int) -> None:
        super().__init__(app)
        self._limit = limit_per_minute
        self._limiter = SlidingWindowLimiter(limit=limit_per_minute)

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._limit <= 0:
            return await call_next(request)
        path = request.url.path
        if path in {"/health", "/ready", "/metrics"} or path.startswith(
            ("/docs", "/openapi")
        ):
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        if not self._limiter.allow(client):
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

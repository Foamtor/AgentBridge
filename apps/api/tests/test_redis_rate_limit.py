"""Redis rate limit tests."""

from __future__ import annotations

import pytest
from middleware.rate_limit import RateLimitMiddleware, RedisSlidingWindowLimiter
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from testing.fake_redis import FakeRedis


@pytest.mark.asyncio
async def test_redis_rate_limit_third_denied() -> None:
    lim = RedisSlidingWindowLimiter(FakeRedis(), limit=2, window_seconds=60)
    assert await lim.allow("ip") is True
    assert await lim.allow("ip") is True
    assert await lim.allow("ip") is False


@pytest.mark.asyncio
async def test_redis_rate_limit_unavailable_returns_503() -> None:
    class _Boom:
        async def eval(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("redis down")

    async def ok(_request):  # noqa: ANN001
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/chat/stream", ok, methods=["POST"])])
    app.add_middleware(
        RateLimitMiddleware, limit_per_minute=10, redis=_Boom()
    )
    with TestClient(app) as c:
        r = c.post("/chat/stream")
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "rate_limit_unavailable"

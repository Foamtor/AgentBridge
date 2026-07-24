"""Redis rate limit tests."""

from __future__ import annotations

import pytest
from middleware.rate_limit import RedisSlidingWindowLimiter
from testing.fake_redis import FakeRedis


@pytest.mark.asyncio
async def test_redis_rate_limit_third_denied() -> None:
    lim = RedisSlidingWindowLimiter(FakeRedis(), limit=2, window_seconds=60)
    assert await lim.allow("ip") is True
    assert await lim.allow("ip") is True
    assert await lim.allow("ip") is False

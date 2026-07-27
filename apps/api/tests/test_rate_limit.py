"""In-process rate limit tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from middleware.rate_limit import SlidingWindowLimiter


def test_sliding_window_third_denied() -> None:
    lim = SlidingWindowLimiter(limit=2, window_seconds=60.0)
    now = 1000.0
    assert lim.allow("k", now=now) is True
    assert lim.allow("k", now=now + 0.1) is True
    assert lim.allow("k", now=now + 0.2) is False


def test_sliding_window_disabled_when_limit_zero() -> None:
    lim = SlidingWindowLimiter(limit=0)
    assert lim.allow("k") is True
    assert lim.allow("k") is True


def test_rate_limit_middleware_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
    os.environ["RATE_LIMIT_PER_MINUTE"] = "2"
    os.environ["AGENTBRIDGE_FAKE_RUNTIME"] = "1"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        r1 = c.post(
            "/chat/stream",
            json={"query": "a", "thread_id": "t-rl-1", "route": "echo"},
        )
        r2 = c.post(
            "/chat/stream",
            json={"query": "b", "thread_id": "t-rl-2", "route": "echo"},
        )
        r3 = c.post(
            "/chat/stream",
            json={"query": "c", "thread_id": "t-rl-3", "route": "echo"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert r3.json()["detail"]["code"] == "rate_limited"

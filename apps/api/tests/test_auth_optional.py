"""Optional auth behavior tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


def test_auth_off_allows_stream_without_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "false"
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        c.app.state.graphs.register("echo", lambda **kw: object())
        c.app.state.tools.register("echo", [])
        r = c.post(
            "/chat/stream",
            json={"query": "hi", "thread_id": "t-auth-off", "route": "echo"},
        )
    assert r.status_code == 200


def test_auth_on_rejects_missing_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    os.environ["AUTH_REQUIRED"] = "true"
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            json={"query": "hi", "thread_id": "t-auth-on", "route": "echo"},
        )
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "unauthorized"

"""Chat stream contract tests (fake runtime, no echo domain)."""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient


def _parse_sse_types(body: str) -> list[str]:
    types: list[str] = []
    for block in body.split("\n\n"):
        line = block.strip()
        if not line.startswith("data: "):
            continue
        payload = json.loads(line[len("data: ") :])
        types.append(payload["type"])
    return types


def test_stream_start_and_done(client):
    r = client.post(
        "/chat/stream",
        json={
            "query": "hi",
            "thread_id": "t-stream-1",
            "route": "echo",
        },
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    types = _parse_sse_types(r.text)
    assert types[0] == "start"
    assert types[-1] == "done"


def test_unknown_route_400(client):
    r = client.post(
        "/chat/stream",
        json={"query": "hi", "thread_id": "t-u", "route": "missing"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "unknown_route"


def test_thread_busy_409(client):
    # Hold the lock so the next stream maps to thread_busy.
    import anyio

    async def _hold():
        await client.app.state.locks.try_acquire("t-busy", "holder")

    anyio.run(_hold)
    r = client.post(
        "/chat/stream",
        json={"query": "hi", "thread_id": "t-busy", "route": "echo"},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "thread_busy"


def test_real_echo_stream_has_text_and_done(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "0")
    # Settings reads bool from env; ensure create_app sees real runtime.
    os.environ["AGENT_BASE_FAKE_RUNTIME"] = "0"
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            json={"query": "hello-echo", "thread_id": "t-echo-real", "route": "echo"},
        )
    assert r.status_code == 200
    types = _parse_sse_types(r.text)
    assert types[0] == "start"
    assert "text_delta" in types
    assert types[-1] == "done"
    assert "hello-echo" in r.text

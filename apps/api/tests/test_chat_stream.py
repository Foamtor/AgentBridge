"""Chat stream contract tests (fake runtime, no echo domain)."""

from __future__ import annotations

import json


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

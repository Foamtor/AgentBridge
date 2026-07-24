"""Chat stream contract tests (fake runtime, no echo domain)."""

from __future__ import annotations

import json

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
    class BlockingRuntime:
        async def astream(self, builder, **kwargs):
            import asyncio

            from agent_base_core.protocol.fragments import OutboundFragment

            yield OutboundFragment(type="text_delta", data={"content": "hold"})
            await asyncio.sleep(2)

    client.app.state.run_lifecycle.replace_runtime(BlockingRuntime())
    tid = "t-busy"
    import threading

    def _hold():
        client.post(
            "/chat/stream",
            json={"query": "hi", "thread_id": tid, "route": "echo"},
        )

    th = threading.Thread(target=_hold)
    th.start()
    import time

    time.sleep(0.1)
    r = client.post(
        "/chat/stream",
        json={"query": "hi", "thread_id": tid, "route": "echo"},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "thread_busy"
    client.post("/chat/cancel", json={"thread_id": tid})
    th.join(timeout=5)


def test_real_echo_stream_has_text_and_done(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "0")
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


def test_runtime_error_single_error_no_rhost(client):
    class BoomRuntime:
        async def astream(self, builder, **kwargs):
            from agent_base_core.protocol.fragments import OutboundFragment

            yield OutboundFragment(type="text_delta", data={"content": "partial"})
            raise RuntimeError("boom")

    client.app.state.run_lifecycle.replace_runtime(BoomRuntime())
    r = client.post(
        "/chat/stream",
        json={"query": "hi", "thread_id": "t-boom", "route": "echo"},
    )
    assert r.status_code == 200
    assert "r-host" not in r.text
    types = _parse_sse_types(r.text)
    assert types.count("error") == 1
    assert types[0] == "start"
    assert types[-1] == "error"
    assert "done" not in types


def test_pre_start_input_failure_is_500_not_empty_200(client):
    def boom_input(query: str, **kwargs):
        raise ValueError("bad input")

    client.app.state.run_lifecycle._input_builders.register("echo", boom_input)
    r = client.post(
        "/chat/stream",
        json={"query": "hi", "thread_id": "t-pre-fail", "route": "echo"},
    )
    assert r.status_code == 500
    assert r.json()["detail"]["code"] == "stream_failed"
    assert "bad input" in r.json()["detail"]["message"]

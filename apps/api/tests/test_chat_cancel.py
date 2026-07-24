"""Chat cancel contract tests."""

from __future__ import annotations

import asyncio
import json
import threading
import time

import anyio
from agent_base_core.protocol.fragments import OutboundFragment


def test_cancel_404_when_idle(client):
    r = client.post("/chat/cancel", json={"thread_id": "t-none"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "run_not_found"


def test_cancel_200_when_registered(client):
    async def _reg():
        await client.app.state.run_lifecycle._test_register_cancel("t-cancel", "r1")

    anyio.run(_reg)
    r = client.post("/chat/cancel", json={"thread_id": "t-cancel", "run_id": "r1"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_cancel_during_stream_emits_cancelled(client):
    class SlowRuntime:
        async def astream(self, builder, **kwargs):
            yield OutboundFragment(type="text_delta", data={"content": "partial"})
            await kwargs["cancel_token"].wait()

    client.app.state.run_lifecycle.replace_runtime(SlowRuntime())
    tid = "t-cancel-stream"
    out: dict = {}

    def _stream():
        with client.stream(
            "POST",
            "/chat/stream",
            json={"query": "hi", "thread_id": tid, "route": "echo"},
        ) as resp:
            out["status"] = resp.status_code
            out["body"] = resp.read().decode("utf-8", errors="replace")

    th = threading.Thread(target=_stream)
    th.start()
    time.sleep(0.15)
    cr = client.post("/chat/cancel", json={"thread_id": tid})
    assert cr.status_code == 200
    th.join(timeout=5)
    assert out.get("status") == 200
    types = []
    for block in out["body"].split("\n\n"):
        line = block.strip()
        if line.startswith("data: "):
            types.append(json.loads(line[6:])["type"])
    assert types[0] == "start"
    assert "cancel_requested" in types
    assert types[-1] == "cancelled"


def test_abort_during_stream_releases_thread_lock(client):
    """After cancel ends a held stream, the same thread_id must not stay busy."""

    class SlowRuntime:
        async def astream(self, builder, **kwargs):
            yield OutboundFragment(type="text_delta", data={"content": "partial"})
            await kwargs["cancel_token"].wait()

    from testing.fake_runtime import ApiFakeRuntime

    client.app.state.run_lifecycle.replace_runtime(SlowRuntime())
    tid = "t-abort-lock"
    out: dict = {}

    def _stream():
        with client.stream(
            "POST",
            "/chat/stream",
            json={"query": "hi", "thread_id": tid, "route": "echo"},
        ) as resp:
            out["status"] = resp.status_code
            out["body"] = resp.read().decode("utf-8", errors="replace")

    th = threading.Thread(target=_stream)
    th.start()
    time.sleep(0.15)
    cr = client.post("/chat/cancel", json={"thread_id": tid})
    assert cr.status_code == 200
    th.join(timeout=5)
    assert th.is_alive() is False
    assert out.get("status") == 200

    # Restore fast fake runtime; assertion is that the lock itself was released.
    client.app.state.run_lifecycle.replace_runtime(ApiFakeRuntime())
    r = client.post(
        "/chat/stream",
        json={"query": "again", "thread_id": tid, "route": "echo"},
    )
    assert r.status_code == 200, f"expected free lock, got {r.status_code}: {r.text[:200]}"

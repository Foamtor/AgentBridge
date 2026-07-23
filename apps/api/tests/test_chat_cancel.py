"""Chat cancel contract tests."""

from __future__ import annotations

import anyio


def test_cancel_404_when_idle(client):
    r = client.post("/chat/cancel", json={"thread_id": "t-none"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "run_not_found"


def test_cancel_200_when_registered(client):
    async def _reg():
        token = object()
        await client.app.state.cancels.register("t-cancel", "r1", token)

    anyio.run(_reg)
    r = client.post("/chat/cancel", json={"thread_id": "t-cancel", "run_id": "r1"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

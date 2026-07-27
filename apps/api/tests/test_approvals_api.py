"""POST /approvals/{id} + demo_approval_write e2e."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for block in body.split("\n\n"):
        line = block.strip()
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


def test_demo_approval_write_and_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    import os

    os.environ["AGENTBRIDGE_FAKE_RUNTIME"] = "0"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            json={
                "query": "please write",
                "thread_id": "t-appr-1",
                "route": "demo_approval_write",
            },
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        assert any(e["type"] == "x.bridge.approval_required" for e in events)
        assert not any(e["type"] == "done" for e in events)
        req = next(e for e in events if e["type"] == "x.bridge.approval_required")
        approval_id = req["data"]["approval_id"]
        run_id = req["run_id"]

        # Same thread new run must not 409 (lock released).
        r2 = c.post(
            "/chat/stream",
            json={
                "query": "hello",
                "thread_id": "t-appr-1",
                "route": "echo",
            },
        )
        assert r2.status_code == 200

        decided = c.post(
            f"/approvals/{approval_id}",
            json={"decision": "approve"},
        )
        assert decided.status_code == 200
        body = decided.json()
        assert body["ok"] is True
        assert body["approval"]["decision"] == "approve"

        run = c.get(f"/runs/{run_id}")
        assert run.status_code == 200
        assert run.json()["status"] == "done"


def test_chat_injects_token_map(client: TestClient) -> None:
    seen: dict = {}
    orig = client.app.state.pipeline.handle

    async def _capture(**kwargs):
        seen["ctx"] = kwargs.get("ctx")
        return await orig(**kwargs)

    client.app.state.pipeline.handle = _capture  # type: ignore[method-assign]
    r = client.post(
        "/chat/stream",
        json={"query": "hi", "thread_id": "t-tm", "route": "echo"},
    )
    assert r.status_code == 200
    assert isinstance(seen["ctx"].metadata.get("token_map"), dict)

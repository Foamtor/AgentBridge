"""M2b gate: messages and events queryable after stream."""

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


def test_threads_messages_and_events_after_stream(client) -> None:
    thread_id = "t-m2b-1"
    r = client.post(
        "/chat/stream",
        json={"query": "hello m2b", "thread_id": thread_id, "route": "echo"},
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    run_id = events[0]["run_id"]
    assert events[-1]["type"] == "done"

    threads = client.get("/threads")
    assert threads.status_code == 200
    assert any(t["thread_id"] == thread_id for t in threads.json())

    msgs = client.get(f"/threads/{thread_id}/messages")
    assert msgs.status_code == 200
    body = msgs.json()
    assert body[0]["role"] == "user"
    assert body[0]["content"] == "hello m2b"
    assert body[1]["role"] == "assistant"
    assert body[1]["content"]  # merged text_delta from fake runtime

    run = client.get(f"/runs/{run_id}")
    assert run.status_code == 200
    assert run.json()["status"] == "done"
    assert run.json()["thread_id"] == thread_id

    ev = client.get(f"/runs/{run_id}/events")
    assert ev.status_code == 200
    types = [e["type"] for e in ev.json()]
    assert types[0] == "start"
    assert "text_delta" in types
    assert types[-1] == "done"


def test_run_not_found_404(client) -> None:
    r = client.get("/runs/r-missing")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "run_not_found"


def test_cross_tenant_run_and_messages_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tenant B must not read tenant A's run/events/messages (Port + REST)."""
    secret = "cross-tenant-secret"
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_DEV_STUB", "false")
    monkeypatch.setenv("OIDC_JWT_SECRET", secret)
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "1")
    import os

    from jose import jwt

    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_DEV_STUB"] = "false"
    os.environ["OIDC_JWT_SECRET"] = secret
    from main import create_app

    app = create_app()
    token_a = jwt.encode(
        {
            "sub": "u-a",
            "tenant_id": "tenant-a",
            "roles": ["admin"],
            "permissions": ["*"],
        },
        secret,
        algorithm="HS256",
    )
    token_b = jwt.encode(
        {
            "sub": "u-b",
            "tenant_id": "tenant-b",
            "roles": ["admin"],
            "permissions": ["*"],
        },
        secret,
        algorithm="HS256",
    )
    thread_id = "t-cross-tenant"
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"query": "hello a", "thread_id": thread_id, "route": "echo"},
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        run_id = events[0]["run_id"]

        own = c.get(
            f"/runs/{run_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert own.status_code == 200

        other_run = c.get(
            f"/runs/{run_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert other_run.status_code == 404

        other_ev = c.get(
            f"/runs/{run_id}/events",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert other_ev.status_code == 404

        other_msgs = c.get(
            f"/threads/{thread_id}/messages",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert other_msgs.status_code == 200
        assert other_msgs.json() == []

        other_threads = c.get(
            "/threads",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert other_threads.status_code == 200
        assert other_threads.json() == []

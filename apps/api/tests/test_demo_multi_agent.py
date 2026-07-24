"""demo_multi_agent emits ≥2 agent_id values in one stream."""

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


def test_demo_multi_agent_two_agent_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "0")
    import os

    os.environ["AGENT_BASE_FAKE_RUNTIME"] = "0"
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            json={
                "query": "collaborate",
                "thread_id": "t-ma-1",
                "route": "demo_multi_agent",
            },
        )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    agent_ids = {
        e["data"].get("agent_id")
        for e in events
        if isinstance(e.get("data"), dict) and e["data"].get("agent_id")
    }
    assert "researcher" in agent_ids
    assert "writer" in agent_ids

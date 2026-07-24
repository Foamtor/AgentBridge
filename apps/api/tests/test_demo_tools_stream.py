"""demo_tools stream contract (real LangGraph runtime, no LLM)."""

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


def test_demo_tools_stream_tool_and_extension(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "0")
    from main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/chat/stream",
            json={
                "query": "add",
                "thread_id": "t-demo-tools-1",
                "route": "demo_tools",
            },
        )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert "tool_call" in types
    assert "tool_result" in types
    assert "x.demo_tools.finished" in types
    assert types[-1] == "done"
    finished = next(e for e in events if e["type"] == "x.demo_tools.finished")
    assert finished["data"]["ok"] is True
    call = next(e for e in events if e["type"] == "tool_call")
    result = next(e for e in events if e["type"] == "tool_result")
    assert call["data"]["tool_call_id"] == "tc-demo-add-1"
    assert result["data"]["tool_call_id"] == "tc-demo-add-1"
    assert result["data"]["ok"] is True

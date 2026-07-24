"""demo_rag stream emits x.bridge.citation."""

from __future__ import annotations

import json

import pytest
from agent_base_core.adapters.fake_retriever import FakeRetriever
from fastapi.testclient import TestClient


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for block in body.split("\n\n"):
        line = block.strip()
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[len("data: ") :]))
    return events


@pytest.mark.asyncio
async def test_demo_rag_emits_citation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_BASE_FAKE_RUNTIME", "0")
    import os

    os.environ["AGENT_BASE_FAKE_RUNTIME"] = "0"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    fake = FakeRetriever()
    await fake.ingest(
        [{"id": "d1", "text": "refund policy 30 days", "tenant_id": "dev"}],
        tenant_id="dev",
    )
    with TestClient(app) as c:
        c.app.state.retriever = fake
        r = c.post(
            "/chat/stream",
            json={
                "query": "refund policy",
                "thread_id": "t-rag-1",
                "route": "demo_rag",
            },
        )
    assert r.status_code == 200
    types = [e["type"] for e in _parse_sse(r.text)]
    assert "x.bridge.citation" in types

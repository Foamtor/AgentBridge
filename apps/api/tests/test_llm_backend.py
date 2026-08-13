"""LLM_BACKEND gateway path + domain uses metadata gateway only."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from agentbridge_core.adapters.alias_llm_gateway import AliasLLMGateway
from agentbridge_core.adapters.fake_chat_model import FakeChatModel
from fastapi.testclient import TestClient


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for block in body.split("\n\n"):
        line = block.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def test_domains_do_not_import_chatopenai() -> None:
    root = Path(__file__).resolve().parents[1] / "domains"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "ChatOpenAI" in text or "langchain_openai" in text:
            offenders.append(str(path.relative_to(root.parent)))
    assert offenders == []


def test_gateway_backend_alias_swap_without_domain_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_MODE", "disabled")
    monkeypatch.setenv("LLM_BACKEND", "gateway")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    os.environ["LLM_BACKEND"] = "gateway"
    os.environ["AGENTBRIDGE_FAKE_RUNTIME"] = "0"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    with TestClient(app) as c:
        # Host swaps alias table; demo_llm graph/tools untouched.
        c.app.state.llm_gateway = AliasLLMGateway(
            {
                "default": FakeChatModel(["swapped-reply"]),
                "fast": FakeChatModel(["fast-reply"]),
            },
            default_alias="default",
        )
        r = c.post(
            "/chat/stream",
            json={
                "query": "ping",
                "thread_id": "t-llm-gw",
                "route": "demo_llm",
            },
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        visible_text = "".join(
            str(event.get("data", {}).get("content", ""))
            for event in events
            if event["type"] == "text_delta"
        )
        assert visible_text == "swapped-reply"


def test_demo_llm_uses_requested_model_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_MODE", "disabled")
    monkeypatch.setenv("LLM_BACKEND", "gateway")
    monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "0")
    os.environ["LLM_BACKEND"] = "gateway"
    os.environ["AGENTBRIDGE_FAKE_RUNTIME"] = "0"
    from testing.app_factory import create_test_app as create_app

    app = create_app()
    with TestClient(app) as c:
        c.app.state.llm_gateway = AliasLLMGateway(
            {
                "default": FakeChatModel(["wrong-default"]),
                "fast": FakeChatModel(["requested-fast"]),
            },
            default_alias="default",
        )
        response = c.post(
            "/chat/stream",
            json={
                "query": "ping",
                "thread_id": "t-llm-selected",
                "route": "demo_llm",
                "model": "fast",
            },
        )

    assert response.status_code == 200
    events = _parse_sse(response.text)
    visible_text = "".join(
        str(event.get("data", {}).get("content", ""))
        for event in events
        if event["type"] == "text_delta"
    )
    assert visible_text == "requested-fast"

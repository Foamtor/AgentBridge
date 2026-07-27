"""LLM_BACKEND gateway path + domain uses metadata gateway only."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from agentbridge_core.adapters.fake_chat_model import FakeChatModel
from agentbridge_core.adapters.alias_llm_gateway import AliasLLMGateway
from fastapi.testclient import TestClient


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
        assert "swapped-reply" in r.text

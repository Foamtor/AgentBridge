"""LangGraph runtime merges graph_config into configurable."""

from __future__ import annotations

from agentbridge_core.application.graph_config import build_graph_config
from agentbridge_core.protocol.context import RUN_CONTEXT_KEY, RunContext, checkpoint_thread_key


def test_build_graph_config_includes_run_context_key() -> None:
    ctx = RunContext(tenant_id="acme", user_id="u1", roles=["admin"])
    cfg = build_graph_config(thread_id="api-1", ctx=ctx)
    assert cfg["configurable"]["thread_id"] == checkpoint_thread_key("acme", "api-1")
    assert cfg["configurable"][RUN_CONTEXT_KEY]["tenant_id"] == "acme"
    assert cfg["configurable"][RUN_CONTEXT_KEY]["user_id"] == "u1"


def test_build_graph_config_default_tenant() -> None:
    ctx = RunContext()
    cfg = build_graph_config(thread_id="t", ctx=ctx)
    assert cfg["storage_key"] == "default::t"

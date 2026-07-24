"""Build LangGraph runnable config from RunContext."""

from __future__ import annotations

from typing import Any

from agent_base_core.protocol.context import RUN_CONTEXT_KEY, RunContext, checkpoint_thread_key


def build_graph_config(*, thread_id: str, ctx: RunContext) -> dict[str, Any]:
    tenant = ctx.tenant_id or "default"
    storage_key = checkpoint_thread_key(tenant, thread_id)
    return {
        "configurable": {
            "thread_id": storage_key,
            RUN_CONTEXT_KEY: ctx.model_dump(),
        },
        "storage_key": storage_key,
    }

"""demo_readonly tools — tenant-scoped order listing."""

from __future__ import annotations

from typing import Annotated, Any

from agent_base_core.protocol.context import get_run_context
from agent_base_core.protocol.tool_meta import attach_tool_meta
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool


@tool
async def list_orders(
    status: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> list[dict[str, Any]]:
    """List orders by status for the current tenant."""
    ctx = get_run_context(config)
    ds = ctx.metadata.get("data_source")
    if ds is None:
        return []
    return await ds.query(
        "SELECT id, status FROM demo_orders WHERE status = $1 AND tenant_id = $2",
        status,
        ctx.tenant_id,
    )


list_orders = attach_tool_meta(list_orders, required_permissions=["order:read"])

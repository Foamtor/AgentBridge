"""Tenant-safe tools for the work-order reference domain."""

from __future__ import annotations

from typing import Annotated, Any

from agentbridge_core.protocol.context import get_run_context
from agentbridge_core.protocol.tool_meta import attach_tool_meta
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool

from domains.work_order_ops.approval import CreateWorkOrderDraft

SAFE_ORDER_FIELDS = ("id", "title", "status", "priority", "assignee_id")


def _source(config: RunnableConfig) -> tuple[Any | None, Any]:
    ctx = get_run_context(config)
    return ctx.metadata.get("data_source"), ctx


@tool
async def list_work_orders(
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> list[dict[str, Any]]:
    """Return display-safe work orders for the current tenant."""
    source, ctx = _source(config)
    if source is None:
        return []
    rows = await source.query(
        "SELECT * FROM work_orders WHERE tenant_id = $1", ctx.tenant_id
    )
    return [{key: row.get(key) for key in SAFE_ORDER_FIELDS} for row in rows]


@tool
async def work_order_statistics(
    dimension: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> dict[str, int]:
    """Count current-tenant work orders by status, priority, or assignee."""
    if dimension not in {"status", "priority", "assignee_id"}:
        raise ValueError("unsupported statistics dimension")
    rows = await list_work_orders.ainvoke({}, config=config)
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(dimension) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


@tool
async def search_work_order_knowledge(
    query: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> list[dict[str, Any]]:
    """Search current-tenant SOP and FAQ knowledge."""
    ctx = get_run_context(config)
    retriever = ctx.metadata.get("retriever")
    if retriever is None:
        return []
    return await retriever.similarity_search(query, tenant_id=ctx.tenant_id, k=3)


@tool
async def prepare_work_order_draft(
    title: str,
    priority: str,
    assignee_id: str,
    ledger_summary: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> dict[str, Any]:
    """Validate and return the immutable draft used by approval."""
    ctx = get_run_context(config)
    draft = CreateWorkOrderDraft(
        draft_id=f"draft-{ctx.run_id or 'work-order'}",
        title=title,
        priority=priority,
        assignee_id=assignee_id,
        ledger_summary=ledger_summary,
    )
    return draft.model_dump()


list_work_orders = attach_tool_meta(
    list_work_orders, required_permissions=["workorder:read"]
)
work_order_statistics = attach_tool_meta(
    work_order_statistics, required_permissions=["workorder:read"]
)
search_work_order_knowledge = attach_tool_meta(
    search_work_order_knowledge, required_permissions=["knowledge:read"]
)
prepare_work_order_draft = attach_tool_meta(
    prepare_work_order_draft,
    required_permissions_all=["workorder:create", "workorder:assign"],
)

"""Tenant-safe tools for the work-order reference domain."""

from __future__ import annotations

from typing import Annotated, Any

from agentbridge_core.protocol.context import get_run_context
from agentbridge_core.protocol.tool_meta import attach_tool_meta
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool

from domains.work_order_ops.approval import CreateWorkOrderDraft

SAFE_ORDER_FIELDS = ("id", "title", "status", "priority", "assignee_id")
WORK_ORDER_DATA_ERROR = "work order data unavailable"
WORK_ORDER_DRAFT_ERROR = "work order draft validation failed"


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
    try:
        rows = await source.query(
            "SELECT * FROM work_orders WHERE tenant_id = $1", ctx.tenant_id
        )
    except Exception as exc:
        raise RuntimeError(WORK_ORDER_DATA_ERROR) from exc
    return [{key: row.get(key) for key in SAFE_ORDER_FIELDS} for row in rows]


@tool
async def work_order_statistics(
    dimension: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> dict[str, int]:
    """Count current-tenant work orders by status, priority, or assignee_id."""
    if dimension == "assignee":
        dimension = "assignee_id"
    if dimension not in {"status", "priority", "assignee_id"}:
        raise ValueError("unsupported statistics dimension")
    source, ctx = _source(config)
    if source is None:
        return {}
    try:
        rows = await source.query(
            "SELECT * FROM work_orders WHERE tenant_id = $1", ctx.tenant_id
        )
    except Exception as exc:
        raise RuntimeError(WORK_ORDER_DATA_ERROR) from exc
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
    try:
        return await retriever.similarity_search(query, tenant_id=ctx.tenant_id, k=3)
    except Exception as exc:
        raise RuntimeError("knowledge retrieval failed") from exc


@tool
async def prepare_work_order_draft(
    title: str,
    priority: str,
    assignee_id: str,
    ledger_summary: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> dict[str, Any]:
    """Validate and return the immutable draft used by approval."""
    source, ctx = _source(config)
    draft = CreateWorkOrderDraft(
        draft_id=f"draft-{ctx.run_id or 'work-order'}",
        title=title,
        priority=priority,
        assignee_id=assignee_id,
        ledger_summary=ledger_summary,
    )
    if source is None:
        raise ValueError("assignee is inactive or unavailable")
    try:
        assignees = await source.query(
            "SELECT * FROM assignees WHERE id = $1 AND tenant_id = $2",
            draft.assignee_id,
            ctx.tenant_id,
        )
    except Exception as exc:
        raise RuntimeError(WORK_ORDER_DRAFT_ERROR) from exc
    if not assignees or not assignees[0].get("active"):
        raise ValueError("assignee is inactive or unavailable")
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

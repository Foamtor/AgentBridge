"""Deterministic graph for lists, statistics, RAG, and approval drafts."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.context import get_run_context
from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from domains.work_order_ops.approval import CreateWorkOrderDraft
from domains.work_order_ops.state import WorkOrderOpsState
from domains.work_order_ops.tools import SAFE_ORDER_FIELDS


def _query_text(state: WorkOrderOpsState) -> str:
    for item in reversed(state.get("messages", [])):
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        if content:
            return str(content)
    return ""


def _chart_type(query: str) -> str:
    lowered = query.lower()
    if "pie" in lowered or "饼" in query:
        return "pie"
    if "line" in lowered or "趋势" in query or "折线" in query:
        return "line"
    return "bar"


def _chart_payload(rows: list[dict[str, Any]], query: str) -> dict[str, Any]:
    categories = sorted({str(row.get("status") or "unknown") for row in rows})
    values = [sum(row.get("status") == category for row in rows) for category in categories]
    chart_type = _chart_type(query)
    series = [{"name": "工单数", "data": values}]
    echarts_series: dict[str, Any] = {
        "name": "工单数",
        "type": chart_type,
        "data": values,
    }
    option: dict[str, Any] = {
        "title": {"text": "按状态统计工单"},
        "tooltip": {"trigger": "item" if chart_type == "pie" else "axis"},
        "series": [echarts_series],
    }
    if chart_type == "pie":
        echarts_series["data"] = [
            {"name": category, "value": value}
            for category, value in zip(categories, values)
        ]
    else:
        option["xAxis"] = {"type": "category", "data": categories}
        option["yAxis"] = {"type": "value", "name": "件"}
    return {
        "schema_version": 1,
        "chart_type": chart_type,
        "title": "按状态统计工单",
        "x_axis": {"label": "状态", "categories": categories},
        "series": series,
        "unit": "件",
        "echarts_option": option,
    }


async def _present(
    state: WorkOrderOpsState, config: RunnableConfig
) -> dict[str, Any]:
    ctx = get_run_context(config)
    query = _query_text(state)
    source = ctx.metadata.get("data_source")
    can_read = "*" in ctx.permissions or "workorder:read" in ctx.permissions
    can_search = "*" in ctx.permissions or "knowledge:read" in ctx.permissions
    can_create = "*" in ctx.permissions or {
        "workorder:create",
        "workorder:assign",
    } <= set(ctx.permissions)
    raw_rows = (
        []
        if source is None or not can_read
        else await source.query(
            "SELECT * FROM work_orders WHERE tenant_id = $1", ctx.tenant_id
        )
    )
    safe_rows = [
        {key: row.get(key) for key in SAFE_ORDER_FIELDS} for row in raw_rows[:100]
    ]
    retriever = ctx.metadata.get("retriever")
    citations = (
        []
        if retriever is None or not can_search
        else await retriever.similarity_search(query, tenant_id=ctx.tenant_id, k=3)
    )
    extensions: list[dict[str, Any]] = [
        {
            "type": "x.work_order_ops.list",
            "data": {
                "schema_version": 1,
                "resource": "work_orders",
                "title": "工单列表",
                "columns": [
                    {"key": key, "label": key, "data_type": "string"}
                    for key in SAFE_ORDER_FIELDS
                ],
                "rows": safe_rows,
                "total": len(raw_rows),
                "truncated": len(raw_rows) > len(safe_rows),
            },
        },
        {"type": "x.work_order_ops.chart", "data": _chart_payload(safe_rows, query)},
        {
            "type": "x.bridge.citation",
            "data": {"citations": citations, "route": "work_order_ops"},
        },
    ]
    if can_create and ("create" in query.lower() or "创建" in query):
        draft = CreateWorkOrderDraft(
            draft_id=f"draft-{ctx.run_id}",
            title="脱敏工单草稿",
            priority="medium",
            assignee_id="assignee-demo-a",
            ledger_summary="待审核创建工单",
        )
        payload = draft.model_dump()
        extensions.extend(
            [
                {
                    "type": "x.work_order_ops.ledger_preview",
                    "data": {
                        "schema_version": 1,
                        "draft_id": draft.draft_id,
                        "work_order": {
                            "title": draft.title,
                            "priority": draft.priority,
                            "assignee_id": draft.assignee_id,
                        },
                        "ledger": {
                            "summary": draft.ledger_summary,
                            "source": "assistant",
                        },
                        "approval_required": True,
                    },
                },
                {
                    "type": "x.bridge.approval_required",
                    "data": {
                        "tool": "create_work_order",
                        "timeout_seconds": 1800,
                        "action": {
                            "type": "work_order_ops.create_v1",
                            "payload": payload,
                        },
                    },
                },
            ]
        )
    return {OUTBOUND_EXTENSIONS_KEY: extensions}


def build_work_order_ops_graph(*, checkpointer: Any = None, **kwargs: Any):
    graph = StateGraph(WorkOrderOpsState)
    graph.add_node("present", _present)
    graph.add_edge(START, "present")
    graph.add_edge("present", END)
    return graph.compile(checkpointer=checkpointer)

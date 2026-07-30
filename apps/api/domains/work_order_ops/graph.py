"""Tool-driven graph for lists, statistics, RAG, and approval drafts."""

from __future__ import annotations

import json
from typing import Any

from agentbridge_core.protocol.context import get_run_context
from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from domains.work_order_ops.approval import CreateWorkOrderDraft
from domains.work_order_ops.state import WorkOrderOpsState
from domains.work_order_ops.tools import SAFE_ORDER_FIELDS

_READ_TOOL_NAMES = frozenset(
    {
        "list_work_orders",
        "work_order_statistics",
        "search_work_order_knowledge",
    }
)
_DRAFT_TOOL_NAME = "prepare_work_order_draft"
_MISSING_FIELDS_MESSAGE = (
    "创建工单需要提供完整字段：title、priority、assignee_id、ledger_summary。"
)
_DRAFT_VALIDATION_MESSAGE = (
    "工单草稿校验失败，请检查 title、priority、assignee_id 和 ledger_summary。"
)
_CREATE_NOT_ALLOWED_MESSAGE = "当前调用方无权创建并分配工单。"


def _query_text(state: WorkOrderOpsState) -> str:
    for item in reversed(state.get("messages", [])):
        if isinstance(item, ToolMessage):
            continue
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content")
        if content:
            return str(content)
    return ""


def _is_create_request(state: WorkOrderOpsState) -> bool:
    if state.get("structured_draft") is not None:
        return True
    query = _query_text(state)
    lowered = query.lower()
    return "create" in lowered or "创建" in query or "新建" in query


def _chart_type(query: str) -> str:
    lowered = query.lower()
    if "pie" in lowered or "饼" in query:
        return "pie"
    if "line" in lowered or "趋势" in query or "折线" in query:
        return "line"
    return "bar"


def _chart_payload(rows: list[dict[str, Any]], query: str) -> dict[str, Any]:
    categories = sorted({str(row.get("status") or "unknown") for row in rows})
    values = [
        sum(row.get("status") == category for row in rows) for category in categories
    ]
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


def _tool_name(tool: Any) -> str:
    return str(getattr(tool, "name", "") or "")


def _plan_reads(
    state: WorkOrderOpsState,
    *,
    available_names: frozenset[str],
) -> dict[str, Any]:
    query = _query_text(state)
    tool_calls: list[dict[str, Any]] = []
    if "list_work_orders" in available_names:
        tool_calls.append(
            {
                "name": "list_work_orders",
                "args": {},
                "id": "tc-work-orders-list",
                "type": "tool_call",
            }
        )
    if "work_order_statistics" in available_names:
        tool_calls.append(
            {
                "name": "work_order_statistics",
                "args": {"dimension": "status"},
                "id": "tc-work-orders-statistics",
                "type": "tool_call",
            }
        )
    if "search_work_order_knowledge" in available_names:
        tool_calls.append(
            {
                "name": "search_work_order_knowledge",
                "args": {"query": query},
                "id": "tc-work-orders-knowledge",
                "type": "tool_call",
            }
        )
    return {"messages": [AIMessage(content="", tool_calls=tool_calls)]}


def _draft_call(args: dict[str, Any], *, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": _DRAFT_TOOL_NAME,
                "args": dict(args),
                "id": call_id,
                "type": "tool_call",
            }
        ],
    )


def _model_draft_call(response: Any) -> AIMessage | None:
    tool_calls = getattr(response, "tool_calls", None)
    if not isinstance(tool_calls, list):
        return None
    for item in tool_calls:
        if not isinstance(item, dict) or item.get("name") != _DRAFT_TOOL_NAME:
            continue
        args = item.get("args")
        if not isinstance(args, dict):
            return None
        call_id = item.get("id")
        return _draft_call(
            args,
            call_id=(
                str(call_id)
                if isinstance(call_id, str) and call_id
                else "tc-work-orders-draft-model"
            ),
        )
    return None


async def _plan_draft(
    state: WorkOrderOpsState,
    config: RunnableConfig,
    *,
    draft_tool: Any | None,
) -> dict[str, Any]:
    if not _is_create_request(state):
        return {"messages": [AIMessage(content="")]}
    if draft_tool is None:
        return {"messages": [AIMessage(content=_CREATE_NOT_ALLOWED_MESSAGE)]}

    structured = state.get("structured_draft")
    if structured is not None:
        return {
            "messages": [
                _draft_call(structured, call_id="tc-work-orders-draft-structured")
            ]
        }

    ctx = get_run_context(config)
    gateway = ctx.metadata.get("llm_gateway")
    if gateway is None:
        return {"messages": [AIMessage(content=_MISSING_FIELDS_MESSAGE)]}
    response = await gateway.chat(
        [{"role": "user", "content": _query_text(state)}],
        ctx=ctx,
        model=state.get("model_alias"),
        tools=[draft_tool],
        tool_choice=_DRAFT_TOOL_NAME,
    )
    call = _model_draft_call(response)
    if call is None:
        return {"messages": [AIMessage(content=_MISSING_FIELDS_MESSAGE)]}
    return {"messages": [call]}


def _route_draft_tools(state: WorkOrderOpsState) -> str:
    for message in reversed(state.get("messages", [])):
        if not isinstance(message, AIMessage):
            continue
        if any(
            call.get("name") == _DRAFT_TOOL_NAME
            for call in message.tool_calls
            if isinstance(call, dict)
        ):
            return "draft_tools"
        return "present"
    return "present"


def _parse_tool_content(content: Any) -> Any:
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _tool_results(state: WorkOrderOpsState, name: str) -> list[tuple[Any, bool]]:
    results: list[tuple[Any, bool]] = []
    for message in state.get("messages", []):
        if not isinstance(message, ToolMessage) or message.name != name:
            continue
        results.append(
            (
                _parse_tool_content(message.content),
                getattr(message, "status", "success") == "error",
            )
        )
    return results


def _read_rows(state: WorkOrderOpsState) -> list[dict[str, Any]]:
    for value, failed in _tool_results(state, "list_work_orders"):
        if not failed and isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _read_citations(state: WorkOrderOpsState) -> list[dict[str, Any]]:
    for value, failed in _tool_results(state, "search_work_order_knowledge"):
        if not failed and isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _read_draft(
    state: WorkOrderOpsState,
) -> tuple[CreateWorkOrderDraft | None, bool]:
    results = _tool_results(state, _DRAFT_TOOL_NAME)
    if not results:
        return None, False
    for value, failed in results:
        if failed:
            return None, True
        try:
            return CreateWorkOrderDraft.model_validate(value), False
        except (TypeError, ValueError):
            return None, True
    return None, True


def _present(state: WorkOrderOpsState) -> dict[str, Any]:
    query = _query_text(state)
    raw_rows = _read_rows(state)
    safe_rows = [
        {key: row.get(key) for key in SAFE_ORDER_FIELDS} for row in raw_rows[:100]
    ]
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
            "data": {
                "citations": _read_citations(state),
                "route": "work_order_ops",
            },
        },
    ]
    draft, invalid_draft = _read_draft(state)
    output: dict[str, Any] = {OUTBOUND_EXTENSIONS_KEY: extensions}
    if invalid_draft:
        output["messages"] = [AIMessage(content=_DRAFT_VALIDATION_MESSAGE)]
        return output
    if draft is None:
        return output

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
    return output


def build_work_order_ops_graph(
    *,
    checkpointer: Any = None,
    tools: Any = None,
    **kwargs: Any,
):
    guarded_tools = list(tools or [])
    available_names = frozenset(
        name
        for tool in guarded_tools
        if (name := _tool_name(tool)) in _READ_TOOL_NAMES | {_DRAFT_TOOL_NAME}
    )
    draft_tool = next(
        (tool for tool in guarded_tools if _tool_name(tool) == _DRAFT_TOOL_NAME),
        None,
    )

    async def plan_draft(
        state: WorkOrderOpsState, config: RunnableConfig
    ) -> dict[str, Any]:
        return await _plan_draft(state, config, draft_tool=draft_tool)

    graph = StateGraph(WorkOrderOpsState)
    graph.add_node(
        "plan_reads",
        lambda state: _plan_reads(state, available_names=available_names),
    )
    graph.add_node("read_tools", ToolNode(guarded_tools))
    graph.add_node("plan_draft", plan_draft)
    graph.add_node(
        "draft_tools",
        ToolNode(
            guarded_tools,
            handle_tool_errors=_DRAFT_VALIDATION_MESSAGE,
        ),
    )
    graph.add_node("present", _present)
    graph.add_edge(START, "plan_reads")
    graph.add_edge("plan_reads", "read_tools")
    graph.add_edge("read_tools", "plan_draft")
    graph.add_conditional_edges(
        "plan_draft",
        _route_draft_tools,
        {
            "draft_tools": "draft_tools",
            "present": "present",
        },
    )
    graph.add_edge("draft_tools", "present")
    graph.add_edge("present", END)
    return graph.compile(checkpointer=checkpointer)

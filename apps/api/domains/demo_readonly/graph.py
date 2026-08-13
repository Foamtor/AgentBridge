"""build_demo_readonly_graph — ToolNode + Fake AIMessage, no ChatModel."""

from __future__ import annotations

import json
from typing import Any

from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from domains.demo_readonly.state import DemoReadonlyState
from domains.demo_readonly.tools import list_orders


def _prepare_tool_call(state: DemoReadonlyState) -> dict[str, Any]:
    query = ""
    for message in reversed(state.get("messages") or []):
        content = getattr(message, "content", None) or (
            message.get("content") if isinstance(message, dict) else None
        )
        if content:
            query = str(content).lower()
            break
    status = "open"
    for candidate in ("open", "closed", "pending"):
        if candidate in query:
            status = candidate
            break
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "list_orders",
                        "args": {"status": status},
                        "id": "tc-demo-readonly-1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }


def _finish(state: DemoReadonlyState) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for message in reversed(state.get("messages") or []):
        if isinstance(message, ToolMessage) and message.name == "list_orders":
            content = message.content
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    content = []
            if isinstance(content, list):
                rows = [row for row in content if isinstance(row, dict)]
            break
    if rows:
        reply = "查询到订单：" + "、".join(
            f"{row.get('id')}（{row.get('status')}）" for row in rows
        )
    else:
        reply = "没有查询到符合条件的模拟订单。"
    return {
        "messages": [AIMessage(content=reply)],
        OUTBOUND_EXTENSIONS_KEY: [
            {
                "type": "x.demo_readonly.finished",
                "data": {"route": "demo_readonly", "ok": True},
            }
        ]
    }


def build_demo_readonly_graph(
    *, checkpointer: Any = None, tools: Any = None, **kwargs: Any
):
    bound = list(tools) if tools else [list_orders]
    graph = StateGraph(DemoReadonlyState)
    graph.add_node("prepare_tool_call", _prepare_tool_call)
    graph.add_node("tools", ToolNode(bound))
    graph.add_node("finish", _finish)
    graph.add_edge(START, "prepare_tool_call")
    graph.add_edge("prepare_tool_call", "tools")
    graph.add_edge("tools", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)

"""build_demo_readonly_graph — ToolNode + Fake AIMessage, no ChatModel."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from domains.demo_readonly.state import DemoReadonlyState
from domains.demo_readonly.tools import list_orders


def _prepare_tool_call(state: DemoReadonlyState) -> dict[str, Any]:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "list_orders",
                        "args": {"status": "open"},
                        "id": "tc-demo-readonly-1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }


def _finish(state: DemoReadonlyState) -> dict[str, Any]:
    return {
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

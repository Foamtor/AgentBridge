"""build_demo_tools_graph — ToolNode + Fake AIMessage, no ChatModel."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from domains.demo_tools.state import DemoToolsState
from domains.demo_tools.tools import add


def _prepare_tool_call(state: DemoToolsState) -> dict[str, Any]:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "add",
                        "args": {"a": 2, "b": 3},
                        "id": "tc-demo-add-1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }


def _finish(state: DemoToolsState) -> dict[str, Any]:
    return {
        OUTBOUND_EXTENSIONS_KEY: [
            {
                "type": "x.demo_tools.finished",
                "data": {"route": "demo_tools", "ok": True},
            }
        ]
    }


def build_demo_tools_graph(*, checkpointer: Any = None, tools: Any = None, **kwargs: Any):
    bound = list(tools) if tools else [add]
    graph = StateGraph(DemoToolsState)
    graph.add_node("prepare_tool_call", _prepare_tool_call)
    graph.add_node("tools", ToolNode(bound))
    graph.add_node("finish", _finish)
    graph.add_edge(START, "prepare_tool_call")
    graph.add_edge("prepare_tool_call", "tools")
    graph.add_edge("tools", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)

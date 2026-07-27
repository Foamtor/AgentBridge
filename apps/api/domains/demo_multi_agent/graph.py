"""demo_multi_agent — researcher then writer on one SSE stream."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from domains.demo_multi_agent.state import DemoMultiAgentState


def _researcher(state: DemoMultiAgentState) -> dict[str, Any]:
    _ = state
    return {
        "messages": [AIMessage(content="research notes")],
        OUTBOUND_EXTENSIONS_KEY: [
            {
                "type": "x.demo_multi_agent.spoke",
                "data": {
                    "agent_id": "researcher",
                    "content": "found sources",
                },
            }
        ],
    }


def _writer(state: DemoMultiAgentState) -> dict[str, Any]:
    _ = state
    return {
        "messages": [AIMessage(content="draft")],
        OUTBOUND_EXTENSIONS_KEY: [
            {
                "type": "x.demo_multi_agent.spoke",
                "data": {
                    "agent_id": "writer",
                    "content": "wrote summary",
                },
            }
        ],
    }


def build_demo_multi_agent_graph(
    *, checkpointer: Any = None, tools: Any = None, **kwargs: Any
):
    _ = tools
    g = StateGraph(DemoMultiAgentState)
    g.add_node("researcher", _researcher)
    g.add_node("writer", _writer)
    g.add_edge(START, "researcher")
    g.add_edge("researcher", "writer")
    g.add_edge("writer", END)
    return g.compile(checkpointer=checkpointer)

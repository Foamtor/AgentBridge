"""build_echo_graph — minimal typed LangGraph for the echo route."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from domains.echo.state import EchoState


def _echo_node(state: EchoState) -> dict[str, Any]:
    query = state.get("query") or ""
    if not query:
        messages = state.get("messages") or []
        if messages:
            first = messages[0]
            query = first if isinstance(first, str) else str(first)
    return {"result": query, "query": query}


def build_echo_graph(*, checkpointer: Any = None, tools: Any = None, **kwargs: Any):
    graph = StateGraph(EchoState)
    graph.add_node("echo_node", _echo_node)
    graph.add_edge(START, "echo_node")
    graph.add_edge("echo_node", END)
    return graph.compile(checkpointer=checkpointer)

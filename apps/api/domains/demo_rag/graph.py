"""demo_rag — tenant-scoped retrieve + x.bridge.citation."""

from __future__ import annotations

from typing import Annotated, Any

from agent_base_core.protocol.context import get_run_context
from agent_base_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from agent_base_core.protocol.tool_meta import attach_tool_meta
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from domains.demo_rag.state import DemoRagState


@tool
async def search_knowledge(
    query: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> list[dict[str, Any]]:
    """Search tenant knowledge base via Retriever in metadata."""
    ctx = get_run_context(config)
    retriever = ctx.metadata.get("retriever")
    if retriever is None:
        return []
    return await retriever.similarity_search(
        query, tenant_id=ctx.tenant_id or "default", k=3
    )


search_knowledge = attach_tool_meta(
    search_knowledge, required_permissions=["knowledge:read"]
)


def _prepare(state: DemoRagState) -> dict[str, Any]:
    q = "policy"
    for m in reversed(state.get("messages") or []):
        content = getattr(m, "content", None) or (
            m.get("content") if isinstance(m, dict) else None
        )
        if content:
            q = str(content)
            break
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_knowledge",
                        "args": {"query": q},
                        "id": "tc-demo-rag-1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }


def _cite(state: DemoRagState) -> dict[str, Any]:
    citations: list[dict[str, Any]] = []
    for m in state.get("messages") or []:
        name = getattr(m, "name", None)
        if name == "search_knowledge":
            content = getattr(m, "content", None)
            if isinstance(content, list):
                for doc in content:
                    if isinstance(doc, dict):
                        citations.append(
                            {
                                "id": doc.get("id"),
                                "text": doc.get("text"),
                                "tenant_id": doc.get("tenant_id"),
                            }
                        )
    return {
        OUTBOUND_EXTENSIONS_KEY: [
            {
                "type": "x.bridge.citation",
                "data": {"citations": citations, "route": "demo_rag"},
            }
        ]
    }


def build_demo_rag_graph(*, checkpointer: Any = None, tools: Any = None, **kwargs: Any):
    bound = list(tools) if tools else [search_knowledge]
    g = StateGraph(DemoRagState)
    g.add_node("prepare", _prepare)
    g.add_node("tools", ToolNode(bound))
    g.add_node("cite", _cite)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "tools")
    g.add_edge("tools", "cite")
    g.add_edge("cite", END)
    return g.compile(checkpointer=checkpointer)

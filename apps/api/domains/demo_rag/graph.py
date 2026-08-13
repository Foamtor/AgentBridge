"""demo_rag — tenant-scoped retrieve + x.bridge.citation."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from agentbridge_core.protocol.context import get_run_context
from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from agentbridge_core.protocol.tool_meta import attach_tool_meta
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from domains.demo_rag.state import DemoRagState

logger = logging.getLogger(__name__)


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
    tenant_id = ctx.tenant_id
    if tenant_id is None or not str(tenant_id).strip():
        raise ValueError("tenant_id is required and must be non-blank")
    return await retriever.similarity_search(
        query, tenant_id=str(tenant_id).strip(), k=3
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


def _tool_docs(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, list):
        return [d for d in content if isinstance(d, dict)]
    if isinstance(content, str) and content.strip():
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [d for d in parsed if isinstance(d, dict)]
    return []


def _normalize_citation(doc: dict[str, Any]) -> dict[str, Any] | None:
    item: dict[str, Any] = {
        "chunk_id": doc.get("chunk_id") or doc.get("id"),
        "doc_id": doc.get("doc_id") or doc.get("chunk_id") or doc.get("id"),
        "text": doc.get("text"),
        "tenant_id": doc.get("tenant_id"),
    }
    required = ("chunk_id", "doc_id", "text", "tenant_id")
    if any(not item.get(k) for k in required):
        logger.warning("skip invalid citation item: missing required fields")
        return None
    if "score" in doc:
        item["score"] = doc["score"]
    return item


def _cite(state: DemoRagState) -> dict[str, Any]:
    citations: list[dict[str, Any]] = []
    for m in state.get("messages") or []:
        name = getattr(m, "name", None)
        if name != "search_knowledge":
            continue
        content = getattr(m, "content", None)
        for doc in _tool_docs(content):
            item = _normalize_citation(doc)
            if item is not None:
                citations.append(item)
    if citations:
        reply = "检索到的处理规范：" + "；".join(
            str(item["text"]).strip() for item in citations[:3]
        )
    else:
        reply = "没有找到与该问题相关的知识库内容。"
    return {
        "messages": [AIMessage(content=reply)],
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

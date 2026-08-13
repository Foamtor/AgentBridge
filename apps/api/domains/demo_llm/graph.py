"""demo_llm — calls LLM only via ctx.metadata['llm_gateway']."""

from __future__ import annotations

from typing import Annotated, Any

from agentbridge_core.protocol.context import get_run_context
from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from agentbridge_core.protocol.tool_meta import attach_tool_meta
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from domains.demo_llm.state import DemoLlmState


@tool
async def ask_model(
    question: str,
    config: Annotated[RunnableConfig, InjectedToolArg],
) -> str:
    """Ask the configured LLM gateway (never constructs a vendor client)."""
    ctx = get_run_context(config)
    gw = ctx.metadata.get("llm_gateway")
    if gw is None:
        return "no_gateway"
    reply = await gw.chat(
        [{"role": "user", "content": question}],
        ctx=ctx,
        model=ctx.metadata.get("llm_model_alias") or None,
    )
    return str(reply)


ask_model = attach_tool_meta(ask_model, required_roles=["admin"])


def _prepare(state: DemoLlmState) -> dict[str, Any]:
    q = ""
    for m in reversed(state.get("messages") or []):
        content = getattr(m, "content", None)
        if isinstance(content, str) and content:
            q = content
            break
        if isinstance(m, dict) and m.get("content"):
            q = str(m["content"])
            break
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "ask_model",
                        "args": {"question": q or "hello"},
                        "id": "tc-demo-llm-1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }


def _finish(state: DemoLlmState) -> dict[str, Any]:
    reply = ""
    for message in reversed(state.get("messages") or []):
        if isinstance(message, ToolMessage):
            reply = str(message.content or "")
            break
    return {
        "messages": [AIMessage(content=reply)],
        OUTBOUND_EXTENSIONS_KEY: [
            {"type": "x.demo_llm.finished", "data": {"route": "demo_llm", "ok": True}}
        ]
    }


def build_demo_llm_graph(*, checkpointer: Any = None, tools: Any = None, **kwargs: Any):
    bound = list(tools) if tools else [ask_model]
    g = StateGraph(DemoLlmState)
    g.add_node("prepare", _prepare)
    g.add_node("tools", ToolNode(bound))
    g.add_node("finish", _finish)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "tools")
    g.add_edge("tools", "finish")
    g.add_edge("finish", END)
    return g.compile(checkpointer=checkpointer)

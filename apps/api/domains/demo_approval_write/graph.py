"""demo_approval_write — HIL pause via x.bridge.approval_required."""

from __future__ import annotations

from typing import Any

from agent_base_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langgraph.graph import END, START, StateGraph

from domains.demo_approval_write.state import DemoApprovalWriteState


def _request_approval(state: DemoApprovalWriteState) -> dict[str, Any]:
    _ = state
    return {
        OUTBOUND_EXTENSIONS_KEY: [
            {
                "type": "x.bridge.approval_required",
                "data": {
                    "tool": "write_record",
                    "timeout_seconds": 30.0,
                },
            }
        ]
    }


def build_demo_approval_write_graph(
    *, checkpointer: Any = None, tools: Any = None, **kwargs: Any
):
    _ = tools
    g = StateGraph(DemoApprovalWriteState)
    g.add_node("request_approval", _request_approval)
    g.add_edge(START, "request_approval")
    g.add_edge("request_approval", END)
    return g.compile(checkpointer=checkpointer)

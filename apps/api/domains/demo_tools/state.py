"""Typed state for the demo_tools domain."""

from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from agent_base_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langgraph.graph.message import add_messages

# Field name must come from protocol constant (no magic string drift).
DemoToolsState = TypedDict(
    "DemoToolsState",
    {
        "messages": Annotated[list, add_messages],
        OUTBOUND_EXTENSIONS_KEY: NotRequired[list],
    },
)

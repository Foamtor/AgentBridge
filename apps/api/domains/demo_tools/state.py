"""Typed state for the demo_tools domain."""

from __future__ import annotations

import operator
from typing import Annotated, NotRequired, TypedDict

from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langgraph.graph.message import add_messages

# Field name must come from protocol constant (no magic string drift).
# Extensions use list append reducer so multiple nodes can contribute.
DemoToolsState = TypedDict(
    "DemoToolsState",
    {
        "messages": Annotated[list, add_messages],
        OUTBOUND_EXTENSIONS_KEY: NotRequired[Annotated[list, operator.add]],
    },
)

from __future__ import annotations

import operator
from typing import Annotated, NotRequired, TypedDict

from agent_base_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY
from langgraph.graph.message import add_messages

DemoMultiAgentState = TypedDict(
    "DemoMultiAgentState",
    {
        "messages": Annotated[list, add_messages],
        OUTBOUND_EXTENSIONS_KEY: NotRequired[Annotated[list, operator.add]],
    },
)

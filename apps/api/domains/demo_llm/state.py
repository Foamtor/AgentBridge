"""demo_llm state."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class DemoLlmState(TypedDict):
    messages: Annotated[list, add_messages]

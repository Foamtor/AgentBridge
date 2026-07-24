"""Typed state for the demo_tools domain."""

from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from langgraph.graph.message import add_messages


class DemoToolsState(TypedDict):
    messages: Annotated[list, add_messages]
    outbound_extensions: NotRequired[list]

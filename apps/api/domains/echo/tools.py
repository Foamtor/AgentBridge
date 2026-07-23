"""Echo domain tools."""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def echo(text: str) -> str:
    """Return the input text unchanged."""
    return text

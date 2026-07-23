"""Typed state for the echo domain."""

from __future__ import annotations

from typing import TypedDict


class EchoState(TypedDict):
    messages: list
    query: str
    result: str

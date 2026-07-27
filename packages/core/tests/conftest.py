"""Shared pytest fixtures for core package tests."""

from __future__ import annotations

import asyncio

import pytest
from agentbridge_core.adapters.sse_event_sink import SseEventSink
from agentbridge_core.registry.graphs import GraphRegistry
from agentbridge_core.registry.tools import ToolRegistry

# Re-export for fixtures only; tests should ``from fakes import …``.
from fakes import (  # noqa: F401
    BadExtensionRuntime,
    BoomRuntime,
    FakeCheckpointerFactory,
    FakeRuntime,
    SlowCancelRuntime,
)


@pytest.fixture
def graphs():
    g = GraphRegistry()
    g.register("echo", lambda **kw: object())
    return g


@pytest.fixture
def tools():
    t = ToolRegistry()
    t.register("echo", [])
    return t


@pytest.fixture
async def queue_and_sink():
    q: asyncio.Queue = asyncio.Queue()
    return q, SseEventSink(q)


async def drain(q: asyncio.Queue) -> list[dict]:
    out: list[dict] = []
    while True:
        item = await q.get()
        if item is None:
            break
        out.append(item)
    return out


@pytest.fixture
def drain_events():
    return drain

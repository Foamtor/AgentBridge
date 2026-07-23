"""Shared pytest fixtures for core package tests."""

from __future__ import annotations

import asyncio

import pytest
from agent_base_core.adapters.sse_event_sink import SseEventSink
from agent_base_core.protocol.events import build_event
from agent_base_core.registry.graphs import GraphRegistry
from agent_base_core.registry.tools import ToolRegistry


class FakeCheckpointerFactory:
    async def setup(self) -> None:
        return None

    async def get(self):
        return None

    async def teardown(self) -> None:
        return None


class FakeRuntime:
    async def astream(self, builder, **kwargs):
        yield build_event(
            "text_delta",
            run_id="r-test",
            sequence=2,
            trace_id="tr",
            data={"content": "ok"},
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

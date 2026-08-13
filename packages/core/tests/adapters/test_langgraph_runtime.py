"""Unit tests for LangGraphRuntime extension + tool mapping."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from agentbridge_core.adapters.langgraph_runtime import LangGraphRuntime
from agentbridge_core.protocol.fragments import (
    OUTBOUND_EXTENSIONS_KEY,
    OutboundFragment,
)


class _FakeCompiled:
    def __init__(self, events: list[dict[str, Any]], state_values: dict[str, Any]):
        self._events = events
        self._state_values = state_values
        self.aget_state_calls: list[Any] = []

    async def astream_events(self, *_args, **_kwargs):
        for evt in self._events:
            yield evt

    async def aget_state(self, config):
        self.aget_state_calls.append(config)
        return SimpleNamespace(values=self._state_values)


class _SlowCompiled(_FakeCompiled):
    async def astream_events(self, *_args, **_kwargs):
        for index, event in enumerate(self._events):
            if index:
                await asyncio.sleep(0.06)
            yield event


@pytest.mark.asyncio
async def test_runtime_yields_tool_result_and_extensions_via_aget_state():
    compiled = _FakeCompiled(
        events=[
            {
                "event": "on_tool_start",
                "name": "add",
                "run_id": "tc-1",
                "data": {"input": {"a": 1, "b": 2}},
            },
            {
                "event": "on_tool_end",
                "name": "add",
                "run_id": "tc-1",
                "data": {"output": "3"},
            },
        ],
        state_values={
            OUTBOUND_EXTENSIONS_KEY: [
                {"type": "x.demo_tools.finished", "data": {"ok": True}},
            ]
        },
    )

    runtime = LangGraphRuntime()
    frags: list[OutboundFragment] = []
    async for frag in runtime.astream(
        lambda **_kw: compiled,
        tools=[],
        checkpointer=None,
        thread_id="t1",
        query="hi",
        cancel_token=None,
    ):
        frags.append(frag)

    assert compiled.aget_state_calls
    assert any(f.type == "tool_call" for f in frags)
    assert any(f.type == "tool_result" for f in frags)
    ext = [f for f in frags if f.type == "x.demo_tools.finished"]
    assert len(ext) == 1
    assert ext[0].data == {"ok": True}


@pytest.mark.asyncio
async def test_runtime_does_not_cancel_graph_events_while_waiting_for_model() -> None:
    compiled = _SlowCompiled(
        events=[
            {"event": "on_chain_start", "name": "plan_reads", "data": {}},
            {
                "event": "on_tool_start",
                "name": "list_work_orders",
                "run_id": "tc-list",
                "data": {"input": {}},
            },
        ],
        state_values={},
    )

    fragments = [
        fragment
        async for fragment in LangGraphRuntime().astream(
            lambda **_kwargs: compiled,
            tools=[],
            checkpointer=None,
            thread_id="thread",
            query="show work orders",
            cancel_token=asyncio.Event(),
        )
    ]

    assert [fragment.type for fragment in fragments] == ["step_update", "tool_call"]


@pytest.mark.asyncio
async def test_runtime_extensions_not_from_on_chain_end_output():
    """Even if on_chain_end output contains the key, we only read via aget_state."""
    compiled = _FakeCompiled(
        events=[
            {
                "event": "on_chain_end",
                "name": "some_node",
                "data": {
                    "output": {
                        OUTBOUND_EXTENSIONS_KEY: [
                            {"type": "x.should.not_emit", "data": {}},
                        ],
                        "result": "hello",
                    }
                },
            }
        ],
        state_values={},  # no extensions in state
    )

    runtime = LangGraphRuntime()
    frags: list[OutboundFragment] = []
    async for frag in runtime.astream(
        lambda **_kw: compiled,
        tools=[],
        checkpointer=None,
        thread_id="t1",
        query="hi",
        cancel_token=None,
    ):
        frags.append(frag)

    assert all(f.type != "x.should.not_emit" for f in frags)
    assert any(f.type == "text_delta" for f in frags)


@pytest.mark.asyncio
async def test_runtime_does_not_project_structured_result_as_assistant_text():
    compiled = _FakeCompiled(
        events=[
            {
                "event": "on_chain_end",
                "name": "structured_node",
                "data": {"output": {"result": {"status": "ok"}}},
            }
        ],
        state_values={},
    )

    fragments = [
        fragment
        async for fragment in LangGraphRuntime().astream(
            lambda **_kwargs: compiled,
            tools=[],
            checkpointer=None,
            thread_id="thread",
            query="show data",
            cancel_token=None,
        )
    ]

    assert all(fragment.type != "text_delta" for fragment in fragments)


@pytest.mark.asyncio
async def test_runtime_no_duplicate_text_when_model_streamed():
    compiled = _FakeCompiled(
        events=[
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": SimpleNamespace(content="Hi")},
            },
            {
                "event": "on_chain_end",
                "name": "agent",
                "data": {"output": {"result": "Hi full"}},
            },
        ],
        state_values={},
    )
    runtime = LangGraphRuntime()
    frags: list[OutboundFragment] = []
    async for frag in runtime.astream(
        lambda **_kw: compiled,
        tools=[],
        checkpointer=None,
        thread_id="t1",
        query="hi",
        cancel_token=None,
    ):
        frags.append(frag)
    texts = [f.data.get("content") for f in frags if f.type == "text_delta"]
    assert texts == ["Hi"]


@pytest.mark.asyncio
async def test_runtime_does_not_project_tool_json_as_assistant_text():
    compiled = _FakeCompiled(
        events=[
            {
                "event": "on_chain_end",
                "name": "read_tools",
                "data": {
                    "output": {
                        "messages": [
                            SimpleNamespace(
                                content='[{"chunk_id": "sop-1"}]',
                                tool_call_id="tc-knowledge",
                            )
                        ]
                    }
                },
            }
        ],
        state_values={},
    )

    fragments = [
        fragment
        async for fragment in LangGraphRuntime().astream(
            lambda **_kwargs: compiled,
            tools=[],
            checkpointer=None,
            thread_id="thread",
            query="search SOP",
            cancel_token=None,
        )
    ]

    assert all(fragment.type != "text_delta" for fragment in fragments)


@pytest.mark.asyncio
async def test_runtime_emits_normalized_model_usage():
    compiled = _FakeCompiled(
        events=[
            {
                "event": "on_chat_model_end",
                "data": {
                    "output": SimpleNamespace(
                        usage_metadata={"input_tokens": 9, "output_tokens": 4}
                    )
                },
            }
        ],
        state_values={},
    )
    runtime = LangGraphRuntime()
    frags: list[OutboundFragment] = []
    async for frag in runtime.astream(
        lambda **_kw: compiled,
        tools=[],
        checkpointer=None,
        thread_id="t1",
        query="hi",
        cancel_token=None,
    ):
        frags.append(frag)

    assert [(frag.type, frag.data) for frag in frags] == [
        ("x.bridge.model_usage", {"input_tokens": 9, "output_tokens": 4})
    ]


@pytest.mark.asyncio
async def test_runtime_tool_error_sets_ok_false():
    compiled = _FakeCompiled(
        events=[
            {
                "event": "on_tool_error",
                "name": "add",
                "run_id": "run-x",
                "data": {"error": "boom", "tool_call_id": "tc-demo-1"},
            }
        ],
        state_values={},
    )
    runtime = LangGraphRuntime()
    frags: list[OutboundFragment] = []
    async for frag in runtime.astream(
        lambda **_kw: compiled,
        tools=[],
        checkpointer=None,
        thread_id="t1",
        query="hi",
        cancel_token=None,
    ):
        frags.append(frag)
    assert len(frags) == 1
    assert frags[0].type == "tool_result"
    assert frags[0].data["ok"] is False
    assert frags[0].data["tool_call_id"] == "tc-demo-1"


@pytest.mark.asyncio
async def test_runtime_tool_call_id_from_aimessage_queue():
    compiled = _FakeCompiled(
        events=[
            {
                "event": "on_chain_end",
                "name": "prepare_tool_call",
                "data": {
                    "output": {
                        "messages": [
                            SimpleNamespace(
                                tool_calls=[
                                    {
                                        "name": "add",
                                        "args": {"a": 1, "b": 2},
                                        "id": "tc-demo-add-1",
                                    }
                                ]
                            )
                        ]
                    }
                },
            },
            {
                "event": "on_tool_start",
                "name": "add",
                "run_id": "lg-run-1",
                "data": {"input": {"a": 1, "b": 2}},
            },
            {
                "event": "on_tool_end",
                "name": "add",
                "run_id": "lg-run-1",
                "data": {
                    "output": SimpleNamespace(content="3", tool_call_id="tc-demo-add-1"),
                    "input": {"a": 1, "b": 2},
                },
            },
        ],
        state_values={},
    )
    runtime = LangGraphRuntime()
    frags: list[OutboundFragment] = []
    async for frag in runtime.astream(
        lambda **_kw: compiled,
        tools=[],
        checkpointer=None,
        thread_id="t1",
        query="hi",
        cancel_token=None,
    ):
        frags.append(frag)
    calls = [f for f in frags if f.type == "tool_call"]
    results = [f for f in frags if f.type == "tool_result"]
    assert calls[0].data["tool_call_id"] == "tc-demo-add-1"
    assert results[0].data["tool_call_id"] == "tc-demo-add-1"


@pytest.mark.asyncio
async def test_runtime_rejects_non_compiled_builder():
    runtime = LangGraphRuntime()
    with pytest.raises(RuntimeError, match="astream_events"):
        async for _ in runtime.astream(
            lambda **_kw: object(),
            tools=[],
            checkpointer=None,
            thread_id="t1",
            query="hi",
            cancel_token=None,
        ):
            pass

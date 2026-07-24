"""LangGraphRuntime adapter — maps graph streaming to OutboundFragment."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from agent_base_core.adapters.event_mapper import (
    map_step_update,
    map_text_delta,
    map_tool_call,
    map_tool_result,
)
from agent_base_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY, OutboundFragment


def _text_from_chain_output(output: Any) -> str | None:
    """Generic domain-agnostic extraction (no hard-coded node names)."""
    if isinstance(output, dict):
        if output.get("result") is not None:
            return str(output["result"])
        messages = output.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            content = getattr(last, "content", None)
            if isinstance(content, str) and content:
                return content
            if isinstance(last, dict) and isinstance(last.get("content"), str):
                return last["content"]
            if isinstance(last, str):
                return last
    content = getattr(output, "content", None)
    if isinstance(content, str) and content:
        return content
    return None


def _summary_from_tool_output(output: Any) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    content = getattr(output, "content", None)
    if isinstance(content, str):
        return content
    return str(output)


class LangGraphRuntime:
    async def astream(
        self,
        builder: Any,
        *,
        tools: Any,
        checkpointer: Any,
        thread_id: str,
        query: str,
        cancel_token: Any,
        extra: dict[str, Any] | None = None,
    ) -> AsyncIterator[OutboundFragment]:
        extra = extra or {}
        graph_input = extra.get("graph_input") or {"messages": [query]}

        compiled = builder(checkpointer=checkpointer, tools=tools) if callable(builder) else builder
        if compiled is None or not hasattr(compiled, "astream_events"):
            if isinstance(cancel_token, asyncio.Event) and cancel_token.is_set():
                return
            yield map_text_delta(query)
            return

        config = {"configurable": {"thread_id": thread_id}}
        stream = compiled.astream_events(graph_input, config=config, version="v2")
        aiter = stream.__aiter__()
        try:
            while True:
                if isinstance(cancel_token, asyncio.Event) and cancel_token.is_set():
                    break
                try:
                    event = await asyncio.wait_for(aiter.__anext__(), timeout=0.05)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

                if isinstance(cancel_token, asyncio.Event) and cancel_token.is_set():
                    break

                kind = event.get("event")
                data = event.get("data") or {}
                name = event.get("name") or ""

                if kind == "on_chain_start" and name and name not in {
                    "LangGraph",
                    "RunnableSequence",
                }:
                    yield map_step_update(name, "running")
                elif kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    content = getattr(chunk, "content", None) if chunk is not None else None
                    if isinstance(content, str) and content:
                        yield map_text_delta(content)
                elif kind == "on_tool_start":
                    yield map_tool_call(
                        event.get("name") or "tool",
                        data.get("input") if isinstance(data.get("input"), dict) else {},
                        str(event.get("run_id") or "tc-unknown"),
                    )
                elif kind == "on_tool_end":
                    output = data.get("output")
                    yield map_tool_result(
                        event.get("name") or "tool",
                        ok=True,
                        tool_call_id=str(event.get("run_id") or "tc-unknown"),
                        summary=_summary_from_tool_output(output),
                    )
                elif kind == "on_chain_end":
                    if name and name not in {"LangGraph", "RunnableSequence"}:
                        yield map_step_update(name, "done")
                    text = _text_from_chain_output(data.get("output"))
                    if text and name and name not in {"LangGraph", "RunnableSequence"}:
                        yield map_text_delta(text)
        finally:
            aclose = getattr(aiter, "aclose", None)
            if callable(aclose):
                try:
                    await aclose()
                except Exception:  # noqa: BLE001
                    pass

        if isinstance(cancel_token, asyncio.Event) and cancel_token.is_set():
            return

        aget_state = getattr(compiled, "aget_state", None)
        if not callable(aget_state):
            return
        snapshot = await aget_state(config)
        values = getattr(snapshot, "values", None) or {}
        if not isinstance(values, dict):
            return
        raw = values.get(OUTBOUND_EXTENSIONS_KEY) or []
        if not isinstance(raw, list):
            return
        for item in raw:
            if not isinstance(item, dict):
                continue
            ext_type = item.get("type")
            if not isinstance(ext_type, str):
                continue
            ext_data = item.get("data") if isinstance(item.get("data"), dict) else {}
            yield OutboundFragment(type=ext_type, data=ext_data or {})

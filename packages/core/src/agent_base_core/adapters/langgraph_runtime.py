"""LangGraphRuntime adapter — maps graph streaming to protocol events."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from agent_base_core.adapters.event_mapper import map_text_delta, map_tool_call


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
    ) -> AsyncIterator[dict[str, Any]]:
        extra = extra or {}
        run_id = str(extra.get("run_id") or "r-unknown")
        trace_id = str(extra.get("trace_id") or run_id)
        # Sequence is provisional; RunLifecycle renumbers outbound events.
        provisional = 1
        graph_input = extra.get("graph_input") or {"messages": [query]}

        compiled = builder(checkpointer=checkpointer, tools=tools) if callable(builder) else builder
        if compiled is None or not hasattr(compiled, "astream_events"):
            if isinstance(cancel_token, asyncio.Event) and cancel_token.is_set():
                return
            yield map_text_delta(query, run_id=run_id, sequence=provisional, trace_id=trace_id)
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
                if kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    content = getattr(chunk, "content", None) if chunk is not None else None
                    if isinstance(content, str) and content:
                        yield map_text_delta(
                            content, run_id=run_id, sequence=provisional, trace_id=trace_id
                        )
                        provisional += 1
                elif kind == "on_tool_start":
                    yield map_tool_call(
                        event.get("name") or "tool",
                        data.get("input") if isinstance(data.get("input"), dict) else {},
                        str(event.get("run_id") or f"tc-{provisional}"),
                        run_id=run_id,
                        sequence=provisional,
                        trace_id=trace_id,
                    )
                    provisional += 1
                elif kind == "on_chain_end":
                    text = _text_from_chain_output(data.get("output"))
                    # Skip graph-level duplicates when node already emitted.
                    name = event.get("name") or ""
                    if text and name and name not in {"LangGraph", "RunnableSequence"}:
                        yield map_text_delta(
                            text, run_id=run_id, sequence=provisional, trace_id=trace_id
                        )
                        provisional += 1
        finally:
            aclose = getattr(aiter, "aclose", None)
            if callable(aclose):
                try:
                    await aclose()
                except Exception:  # noqa: BLE001
                    pass
            if isinstance(cancel_token, asyncio.Event) and cancel_token.is_set():
                # Best-effort: cancel the underlying async generator task if still open.
                pass

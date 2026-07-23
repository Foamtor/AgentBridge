"""LangGraphRuntime adapter — maps graph streaming to protocol events."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from agent_base_core.adapters.event_mapper import map_text_delta, map_tool_call


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
        sequence = int(extra.get("sequence_start") or 2)
        graph_input = extra.get("graph_input") or {"messages": [query]}

        compiled = builder(checkpointer=checkpointer, tools=tools) if callable(builder) else builder
        if compiled is None or not hasattr(compiled, "astream_events"):
            # Placeholder graphs (unit tests) emit a single text delta.
            if isinstance(cancel_token, asyncio.Event) and cancel_token.is_set():
                return
            yield map_text_delta(query, run_id=run_id, sequence=sequence, trace_id=trace_id)
            return

        config = {"configurable": {"thread_id": thread_id}}
        async for event in compiled.astream_events(graph_input, config=config, version="v2"):
            if isinstance(cancel_token, asyncio.Event) and cancel_token.is_set():
                break
            kind = event.get("event")
            data = event.get("data") or {}
            if kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                content = getattr(chunk, "content", None) if chunk is not None else None
                if isinstance(content, str) and content:
                    yield map_text_delta(
                        content, run_id=run_id, sequence=sequence, trace_id=trace_id
                    )
                    sequence += 1
            elif kind == "on_tool_start":
                yield map_tool_call(
                    event.get("name") or "tool",
                    data.get("input") if isinstance(data.get("input"), dict) else {},
                    str(event.get("run_id") or f"tc-{sequence}"),
                    run_id=run_id,
                    sequence=sequence,
                    trace_id=trace_id,
                )
                sequence += 1
            elif kind == "on_chain_end" and event.get("name") == "echo_node":
                output = data.get("output") or {}
                result = output.get("result") if isinstance(output, dict) else None
                if result:
                    yield map_text_delta(
                        str(result), run_id=run_id, sequence=sequence, trace_id=trace_id
                    )
                    sequence += 1

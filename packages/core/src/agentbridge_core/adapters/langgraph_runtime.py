"""LangGraphRuntime adapter — maps graph streaming to OutboundFragment."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from agentbridge_core.adapters.event_mapper import (
    map_step_update,
    map_text_delta,
    map_tool_call,
    map_tool_result,
)
from agentbridge_core.protocol.fragments import OUTBOUND_EXTENSIONS_KEY, OutboundFragment

logger = logging.getLogger(__name__)

# Framework wrapper names — not domain steps / text sources.
_SKIP_CHAIN_NAMES = frozenset({"LangGraph", "RunnableSequence"})


def _content_to_text(content: Any) -> str | None:
    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str) and text:
                    parts.append(text)
        joined = "".join(parts)
        return joined or None
    return None


def _text_from_chain_output(output: Any) -> str | None:
    """Generic domain-agnostic extraction (no hard-coded node names)."""
    if isinstance(output, dict):
        if output.get("result") is not None:
            return str(output["result"])
        messages = output.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            text = _content_to_text(getattr(last, "content", None))
            if text:
                return text
            if isinstance(last, dict):
                text = _content_to_text(last.get("content"))
                if text:
                    return text
            if isinstance(last, str):
                return last
    text = _content_to_text(getattr(output, "content", None))
    if text:
        return text
    return None


def _summary_from_tool_output(output: Any) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    text = _content_to_text(getattr(output, "content", None))
    if text is not None:
        return text
    return str(output)


def _tool_call_ids_from_chain_output(output: Any) -> list[str]:
    """Collect AIMessage.tool_calls[].id from a node output (FIFO for ToolNode)."""
    messages: list[Any] = []
    if isinstance(output, dict) and isinstance(output.get("messages"), list):
        messages = output["messages"]
    elif hasattr(output, "tool_calls"):
        messages = [output]
    ids: list[str] = []
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls is None and isinstance(msg, dict):
            tool_calls = msg.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tc in tool_calls:
            if isinstance(tc, dict):
                tid = tc.get("id")
            else:
                tid = getattr(tc, "id", None)
            if isinstance(tid, str) and tid:
                ids.append(tid)
    return ids


def _tool_call_id_from_output(output: Any) -> str | None:
    tid = getattr(output, "tool_call_id", None)
    if isinstance(tid, str) and tid:
        return tid
    if isinstance(output, dict):
        tid = output.get("tool_call_id")
        if isinstance(tid, str) and tid:
            return tid
    return None


def _tool_call_id_fallback(event: dict[str, Any], data: dict[str, Any]) -> str:
    for key in ("tool_call_id", "id"):
        val = data.get(key)
        if isinstance(val, str) and val:
            return val
    inp = data.get("input")
    if isinstance(inp, dict):
        for key in ("tool_call_id", "id"):
            val = inp.get(key)
            if isinstance(val, str) and val:
                return val
    fallback = str(event.get("run_id") or "tc-unknown")
    if fallback == "tc-unknown":
        logger.warning(
            "tool_call_id missing; using fallback %r (event name=%r)",
            fallback,
            event.get("name"),
        )
    else:
        logger.warning(
            "tool_call_id missing; falling back to LangChain run_id=%r (event name=%r)",
            fallback,
            event.get("name"),
        )
    return fallback


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
            raise RuntimeError(
                "graph builder did not return a compiled graph with astream_events"
            )

        graph_cfg = extra.get("graph_config")
        if isinstance(graph_cfg, dict) and isinstance(graph_cfg.get("configurable"), dict):
            config = {
                "configurable": {
                    **graph_cfg["configurable"],
                    "thread_id": graph_cfg["configurable"].get("thread_id", thread_id),
                }
            }
        else:
            config = {"configurable": {"thread_id": thread_id}}
        stream = compiled.astream_events(graph_input, config=config, version="v2")
        aiter = stream.__aiter__()
        streamed_model_text = False
        pending_tool_call_ids: list[str] = []
        run_id_to_tool_call_id: dict[str, str] = {}
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
                    raise

                if isinstance(cancel_token, asyncio.Event) and cancel_token.is_set():
                    break

                kind = event.get("event")
                data = event.get("data") or {}
                name = event.get("name") or ""
                run_id = str(event.get("run_id") or "")

                if kind == "on_chain_start" and name and name not in _SKIP_CHAIN_NAMES:
                    yield map_step_update(name, "running")
                elif kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    content = getattr(chunk, "content", None) if chunk is not None else None
                    text = _content_to_text(content)
                    if text:
                        streamed_model_text = True
                        yield map_text_delta(text)
                elif kind == "on_tool_start":
                    if pending_tool_call_ids:
                        tool_call_id = pending_tool_call_ids.pop(0)
                    else:
                        tool_call_id = _tool_call_id_fallback(event, data)
                    if run_id:
                        run_id_to_tool_call_id[run_id] = tool_call_id
                    yield map_tool_call(
                        event.get("name") or "tool",
                        data.get("input") if isinstance(data.get("input"), dict) else {},
                        tool_call_id,
                    )
                elif kind == "on_tool_end":
                    output = data.get("output")
                    tool_call_id = (
                        _tool_call_id_from_output(output)
                        or run_id_to_tool_call_id.get(run_id)
                        or _tool_call_id_fallback(event, data)
                    )
                    yield map_tool_result(
                        event.get("name") or "tool",
                        ok=True,
                        tool_call_id=tool_call_id,
                        summary=_summary_from_tool_output(output),
                    )
                elif kind == "on_tool_error":
                    err = data.get("error")
                    tool_call_id = (
                        run_id_to_tool_call_id.get(run_id)
                        or _tool_call_id_fallback(event, data)
                    )
                    yield map_tool_result(
                        event.get("name") or "tool",
                        ok=False,
                        tool_call_id=tool_call_id,
                        summary=str(err) if err is not None else "tool error",
                    )
                elif kind == "on_chain_end":
                    pending_tool_call_ids.extend(
                        _tool_call_ids_from_chain_output(data.get("output"))
                    )
                    if name and name not in _SKIP_CHAIN_NAMES:
                        yield map_step_update(name, "done")
                    # Prefer token stream; only fallback to full node output when
                    # no chat model stream was seen (e.g. echo-style nodes).
                    if not streamed_model_text:
                        text = _text_from_chain_output(data.get("output"))
                        if text and name and name not in _SKIP_CHAIN_NAMES:
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

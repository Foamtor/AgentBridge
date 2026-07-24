"""project_turn merges text_delta and writes run status."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.memory_event_log import MemoryEventLog
from agent_base_core.adapters.memory_message_store import MemoryMessageStore
from agent_base_core.adapters.memory_run_store import MemoryRunStore
from agent_base_core.application.project_turn import project_turn


@pytest.mark.asyncio
async def test_project_turn_merges_deltas_and_isolates_tenant() -> None:
    event_log = MemoryEventLog()
    messages = MemoryMessageStore()
    runs = MemoryRunStore()
    run_id = "r-proj"
    await event_log.append(
        run_id, {"type": "start", "run_id": run_id, "sequence": 1}, tenant_id="acme"
    )
    await event_log.append(
        run_id,
        {
            "type": "text_delta",
            "run_id": run_id,
            "sequence": 2,
            "data": {"content": "hel"},
        },
        tenant_id="acme",
    )
    await event_log.append(
        run_id,
        {
            "type": "text_delta",
            "run_id": run_id,
            "sequence": 3,
            "data": {"content": "lo"},
        },
        tenant_id="acme",
    )
    await event_log.append(
        run_id, {"type": "done", "run_id": run_id, "sequence": 4}, tenant_id="acme"
    )
    await project_turn(
        event_log=event_log,
        message_store=messages,
        run_store=runs,
        tenant_id="acme",
        thread_id="th-1",
        run_id=run_id,
        query="say hi",
        terminal="done",
    )
    msgs = await messages.list_messages("acme", "th-1")
    assert msgs[0] == {"role": "user", "content": "say hi", "run_id": run_id}
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "hello"
    assert (await runs.get(run_id))["status"] == "done"
    assert await messages.list_messages("other", "th-1") == []

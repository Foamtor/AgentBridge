"""MemoryEventLog append/list tests."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.memory_event_log import MemoryEventLog


@pytest.mark.asyncio
async def test_memory_event_log_append_and_list() -> None:
    log = MemoryEventLog()
    e1 = {"run_id": "r1", "type": "start", "sequence": 1}
    e2 = {"run_id": "r1", "type": "text_delta", "sequence": 2, "data": {"content": "a"}}
    await log.append("r1", e1)
    await log.append("r1", e2)
    assert await log.list("r1") == [e1, e2]
    assert await log.list("missing") == []

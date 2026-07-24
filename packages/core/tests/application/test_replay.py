"""replay_run returns EventLog list order."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.memory_event_log import MemoryEventLog
from agent_base_core.application.replay import replay_run


@pytest.mark.asyncio
async def test_replay_run_returns_committed_events() -> None:
    log = MemoryEventLog()
    await log.append("r1", {"type": "start", "run_id": "r1", "sequence": 1}, tenant_id="t")
    await log.append("r1", {"type": "done", "run_id": "r1", "sequence": 2}, tenant_id="t")
    events = await replay_run(log, "r1", tenant_id="t")
    assert [e["type"] for e in events] == ["start", "done"]
    assert await replay_run(log, "r1", tenant_id="other") == []

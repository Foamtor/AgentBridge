"""MemoryEventLog append/list tests."""

from __future__ import annotations

import pytest
from agentbridge_core.adapters.memory_event_log import MemoryEventLog


@pytest.mark.asyncio
async def test_memory_event_log_append_and_list() -> None:
    log = MemoryEventLog()
    e1 = {"run_id": "r1", "type": "start", "sequence": 1}
    e2 = {"run_id": "r1", "type": "text_delta", "sequence": 2, "data": {"content": "a"}}
    await log.append("r1", e1, tenant_id="acme")
    await log.append("r1", e2, tenant_id="acme")
    assert await log.list("r1", tenant_id="acme") == [e1, e2]
    assert await log.list("missing", tenant_id="acme") == []
    assert await log.list("r1", tenant_id="other") == []


@pytest.mark.asyncio
async def test_memory_event_log_rejects_cross_tenant_append() -> None:
    log = MemoryEventLog()
    await log.append("r1", {"type": "start"}, tenant_id="acme")
    with pytest.raises(PermissionError, match="cross_tenant"):
        await log.append("r1", {"type": "done"}, tenant_id="other")

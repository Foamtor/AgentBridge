"""Memory message/run store tenant isolation."""

from __future__ import annotations

import pytest
from agent_base_core.adapters.memory_message_store import MemoryMessageStore
from agent_base_core.adapters.memory_run_store import MemoryRunStore


@pytest.mark.asyncio
async def test_message_store_tenant_isolation() -> None:
    store = MemoryMessageStore()
    await store.append_message("t1", "th", {"role": "user", "content": "hi"})
    assert len(await store.list_messages("t1", "th")) == 1
    assert await store.list_messages("other", "th") == []


@pytest.mark.asyncio
async def test_run_store_upsert_and_list() -> None:
    store = MemoryRunStore()
    await store.upsert(
        {"run_id": "r1", "tenant_id": "t1", "thread_id": "th", "status": "done"}
    )
    assert (await store.get("r1"))["status"] == "done"
    assert len(await store.list_by_tenant("t1")) == 1
    assert await store.list_by_tenant("other") == []

import pytest

from agent_base_core.adapters.memory_audit_logger import MemoryAuditLogger


@pytest.mark.asyncio
async def test_audit_records_append():
    log = MemoryAuditLogger()
    await log.log(
        user_id="u",
        tenant_id="t",
        action="invoke_tool",
        resource="delete",
        detail={"decision": "deny"},
        result="denied",
    )
    assert len(log.records) == 1
    assert log.records[0]["action"] == "invoke_tool"

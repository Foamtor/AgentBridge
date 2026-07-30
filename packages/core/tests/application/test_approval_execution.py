"""Approval execution state-machine tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from agentbridge_core.adapters.memory_approval_store import MemoryApprovalStore


async def _approved_store() -> tuple[MemoryApprovalStore, str]:
    store = MemoryApprovalStore()
    approval_id = await store.create({"tenant_id": "acme"})
    approved = await store.decide(approval_id, tenant_id="acme", decision="approve")
    assert approved is not None
    return store, approval_id


@pytest.mark.asyncio
async def test_approval_claim_is_single_consumer() -> None:
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    store = MemoryApprovalStore()
    approval_id = await store.create(
        {"tenant_id": "acme", "status": "approved_pending_execution"}
    )

    first, second = await asyncio.gather(
        store.claim_execution(approval_id, tenant_id="acme", now=t0, lease_seconds=60),
        store.claim_execution(approval_id, tenant_id="acme", now=t0, lease_seconds=60),
    )

    assert sum(item is not None for item in (first, second)) == 1


@pytest.mark.asyncio
async def test_approval_succeeds_once_and_persists_result() -> None:
    store, approval_id = await _approved_store()
    t0 = datetime(2026, 7, 30, tzinfo=UTC)

    claimed = await store.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=60
    )
    assert claimed and claimed["status"] == "executing"
    assert claimed["execution_lease_expires_at"] == t0 + timedelta(seconds=60)

    succeeded = await store.mark_succeeded(
        approval_id,
        tenant_id="acme",
        execution_token=claimed["execution_token"],
        result={"fragments": [{"type": "created"}]},
    )
    assert succeeded and succeeded["status"] == "succeeded"
    assert succeeded["result"] == {"fragments": [{"type": "created"}]}
    assert (
        await store.claim_execution(
            approval_id, tenant_id="acme", now=t0, lease_seconds=60
        )
        is None
    )


@pytest.mark.asyncio
async def test_approval_failure_can_be_retried_after_execution_claim() -> None:
    store, approval_id = await _approved_store()
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    claimed = await store.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=60
    )
    assert claimed

    failed = await store.mark_retryable_failed(
        approval_id,
        tenant_id="acme",
        execution_token=claimed["execution_token"],
        error="database unavailable",
    )
    assert failed and failed["status"] == "retryable_failed"
    assert failed["error"] == "database unavailable"
    assert await store.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=60
    )


@pytest.mark.asyncio
async def test_denied_or_execution_denied_approvals_cannot_be_claimed() -> None:
    store = MemoryApprovalStore()
    denied_id = await store.create({"tenant_id": "acme"})
    denied = await store.decide(
        denied_id, tenant_id="acme", decision="deny", reason="deny"
    )
    assert denied and denied["status"] == "denied" and denied["reason"] == "deny"
    assert await store.claim_execution(
        denied_id, tenant_id="acme", now=datetime.now(UTC), lease_seconds=60
    ) is None

    store, approved_id = await _approved_store()
    execution_denied = await store.mark_execution_denied(
        approved_id, tenant_id="acme", reason="requester_policy_denied"
    )
    assert execution_denied and execution_denied["reason"] == "requester_policy_denied"
    assert await store.claim_execution(
        approved_id, tenant_id="acme", now=datetime.now(UTC), lease_seconds=60
    ) is None


@pytest.mark.asyncio
async def test_approval_execution_tenant_and_lease_guards() -> None:
    store, approval_id = await _approved_store()
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    assert await store.get(approval_id, tenant_id="other") is None
    assert await store.claim_execution(
        approval_id, tenant_id="other", now=t0, lease_seconds=10
    ) is None

    assert await store.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=10
    )
    assert await store.recover_expired_execution(
        approval_id, tenant_id="acme", now=t0 + timedelta(seconds=9)
    ) is None
    recovered = await store.recover_expired_execution(
        approval_id, tenant_id="acme", now=t0 + timedelta(seconds=10)
    )
    assert recovered and recovered["status"] == "retryable_failed"
    assert recovered["error"] == "execution_lease_expired"
    assert await store.claim_execution(
        approval_id, tenant_id="acme", now=t0 + timedelta(seconds=10), lease_seconds=10
    )


@pytest.mark.asyncio
async def test_result_delivery_failure_does_not_make_success_reexecutable() -> None:
    store, approval_id = await _approved_store()
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    claimed = await store.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=60
    )
    assert claimed
    assert await store.mark_succeeded(
        approval_id,
        tenant_id="acme",
        execution_token=claimed["execution_token"],
        result={},
    )

    delivery_failed = await store.mark_result_delivery_failed(
        approval_id, tenant_id="acme", error="event log unavailable"
    )
    assert delivery_failed and delivery_failed["status"] == "succeeded"
    assert delivery_failed["result_delivery_error"] == "event log unavailable"
    assert await store.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=60
    ) is None


@pytest.mark.asyncio
async def test_expired_worker_cannot_finish_new_execution_claim() -> None:
    store, approval_id = await _approved_store()
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    old = await store.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=1
    )
    assert old and old["execution_token"]
    assert await store.recover_expired_execution(
        approval_id, tenant_id="acme", now=t0 + timedelta(seconds=2)
    )
    new = await store.claim_execution(
        approval_id,
        tenant_id="acme",
        now=t0 + timedelta(seconds=2),
        lease_seconds=60,
    )
    assert new and new["execution_token"] != old["execution_token"]
    assert (
        await store.mark_succeeded(
            approval_id,
            tenant_id="acme",
            execution_token=old["execution_token"],
            result={"worker": "old"},
        )
        is None
    )
    succeeded = await store.mark_succeeded(
        approval_id,
        tenant_id="acme",
        execution_token=new["execution_token"],
        result={"worker": "new"},
    )
    assert succeeded and succeeded["result"] == {"worker": "new"}


@pytest.mark.asyncio
async def test_approval_sequence_is_atomic_and_monotonic() -> None:
    store = MemoryApprovalStore()
    approval_id = await store.create(
        {"tenant_id": "acme", "sequence": 7, "last_sequence": 7}
    )
    values = await asyncio.gather(
        *(store.next_sequence(approval_id, tenant_id="acme") for _ in range(4))
    )
    assert sorted(values) == [8, 9, 10, 11]


@pytest.mark.asyncio
async def test_store_lists_only_expired_pending_records() -> None:
    store = MemoryApprovalStore()
    now = datetime(2026, 7, 30, tzinfo=UTC)
    expired = await store.create(
        {
            "tenant_id": "acme",
            "status": "pending",
            "approval_expires_at": now - timedelta(seconds=1),
        }
    )
    await store.create(
        {
            "tenant_id": "acme",
            "status": "pending",
            "approval_expires_at": now + timedelta(seconds=30),
        }
    )
    rows = await store.list_expired_pending(now=now)
    assert [row["approval_id"] for row in rows] == [expired]


@pytest.mark.asyncio
async def test_retryable_execution_can_be_denied_before_reclaim() -> None:
    store, approval_id = await _approved_store()
    t0 = datetime(2026, 7, 30, tzinfo=UTC)
    claimed = await store.claim_execution(
        approval_id, tenant_id="acme", now=t0, lease_seconds=60
    )
    assert claimed
    assert await store.mark_retryable_failed(
        approval_id,
        tenant_id="acme",
        execution_token=claimed["execution_token"],
        error="temporary",
    )

    denied = await store.mark_execution_denied(
        approval_id, tenant_id="acme", reason="policy_changed"
    )
    assert denied and denied["status"] == "denied"

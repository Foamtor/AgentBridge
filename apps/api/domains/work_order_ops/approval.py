"""Approved work-order creation action; all writes are transaction-scoped."""

from __future__ import annotations

from typing import Any, Literal

from agentbridge_core.ports.data_source import TransactionalDataSource
from agentbridge_core.protocol.context import RunContext
from agentbridge_core.protocol.fragments import OutboundFragment
from pydantic import BaseModel, Field


class CreateWorkOrderDraft(BaseModel):
    draft_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=3, max_length=120)
    priority: Literal["low", "medium", "high"]
    assignee_id: str = Field(min_length=1, max_length=64)
    ledger_summary: str = Field(min_length=3, max_length=500)


def make_create_work_order_handler(data_source: TransactionalDataSource):
    async def handler(
        *,
        action: dict[str, Any],
        requester_ctx: RunContext,
        approval_id: str,
    ) -> list[OutboundFragment]:
        draft = CreateWorkOrderDraft.model_validate(action.get("payload"))
        tenant_id = requester_ctx.tenant_id

        async def write(tx: Any) -> tuple[str, str, str]:
            orders = await tx.query(
                "SELECT * FROM work_orders "
                "WHERE approval_id = $1 AND tenant_id = $2",
                approval_id,
                tenant_id,
            )
            ledgers = await tx.query(
                "SELECT * FROM ledgers "
                "WHERE approval_id = $1 AND tenant_id = $2",
                approval_id,
                tenant_id,
            )
            if orders and ledgers:
                order, ledger = orders[0], ledgers[0]
                return order["id"], ledger["id"], order["assignee_id"]
            if orders or ledgers:
                raise RuntimeError("inconsistent approval records")

            assignees = await tx.query(
                "SELECT * FROM assignees WHERE id = $1 AND tenant_id = $2",
                draft.assignee_id,
                tenant_id,
            )
            if not assignees or not assignees[0].get("active"):
                raise ValueError("assignee is inactive or unavailable")

            work_order_id = f"WO-{approval_id}"
            ledger_id = f"LG-{approval_id}"
            await tx.execute(
                "INSERT INTO work_orders "
                "(id, tenant_id, approval_id, title, status, priority, assignee_id) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                work_order_id,
                tenant_id,
                approval_id,
                draft.title,
                "open",
                draft.priority,
                draft.assignee_id,
            )
            await tx.execute(
                "INSERT INTO ledgers "
                "(id, tenant_id, approval_id, work_order_id, summary) "
                "VALUES ($1, $2, $3, $4, $5)",
                ledger_id,
                tenant_id,
                approval_id,
                work_order_id,
                draft.ledger_summary,
            )
            return work_order_id, ledger_id, draft.assignee_id

        work_order_id, ledger_id, assignee_id = await data_source.transaction(write)
        return [
            OutboundFragment(
                type="x.work_order_ops.work_order_created",
                data={
                    "schema_version": 1,
                    "work_order_id": work_order_id,
                    "ledger_id": ledger_id,
                    "assignee_id": assignee_id,
                    "status": "open",
                },
            )
        ]

    return handler

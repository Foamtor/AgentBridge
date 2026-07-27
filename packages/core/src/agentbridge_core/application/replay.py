"""Replay helpers for committed EventLog envelopes."""

from __future__ import annotations

from typing import Any

from agentbridge_core.ports.event_log import EventLog


async def replay_run(
    event_log: EventLog, run_id: str, *, tenant_id: str
) -> list[dict[str, Any]]:
    """Return committed events for run_id in append order (tenant-scoped)."""
    return await event_log.list(run_id, tenant_id=tenant_id)

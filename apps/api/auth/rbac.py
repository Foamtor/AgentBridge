"""Admin permission helper."""

from __future__ import annotations

from fastapi import HTTPException

from agentbridge_core.protocol.context import RunContext


def require_permission(ctx: RunContext, perm: str) -> None:
    if "*" in ctx.permissions or perm in ctx.permissions:
        return
    raise HTTPException(
        status_code=403,
        detail={"code": "forbidden", "message": f"missing {perm}"},
    )

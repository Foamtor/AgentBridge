"""Map JWT claims / auth settings to RunContext (phase A — identity only)."""

from __future__ import annotations

from typing import Any, Mapping

from agentbridge_core.protocol.context import RunContext


def claims_to_run_context(
    claims: Mapping[str, Any] | None,
    *,
    auth_required: bool,
    policy_bundle_version: str = "",
) -> RunContext:
    """Build identity RunContext from optional JWT claims.

    Dev default (admin + ``*``) only when ``auth_required`` is False.
    When auth is required and claims are missing, return an empty identity
    (no elevated roles/permissions).
    ``policy_bundle_version`` comes from host config (not JWT).
    """
    if not auth_required:
        return RunContext(
            user_id="dev",
            tenant_id="dev",
            roles=["admin"],
            permissions=["*"],
            policy_bundle_version=policy_bundle_version,
        )

    if claims is None:
        return RunContext(policy_bundle_version=policy_bundle_version)

    roles_raw = claims.get("roles") or []
    if isinstance(roles_raw, str):
        roles = [roles_raw]
    else:
        roles = [str(r) for r in roles_raw]

    perms_raw = claims.get("permissions")
    if perms_raw is None:
        perms_raw = claims.get("perms") or []
    if isinstance(perms_raw, str):
        permissions = [perms_raw]
    else:
        permissions = [str(p) for p in perms_raw]

    tenant = claims.get("tenant_id") or claims.get("tid") or ""
    return RunContext(
        user_id=str(claims.get("sub") or ""),
        tenant_id=str(tenant),
        roles=roles,
        permissions=permissions,
        policy_bundle_version=policy_bundle_version,
    )

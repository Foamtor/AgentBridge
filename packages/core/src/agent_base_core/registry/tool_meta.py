"""Tool permission metadata helpers."""

from __future__ import annotations

from typing import Any

_META_ATTR = "_agent_bridge_tool_meta"


def attach_tool_meta(
    tool: Any,
    *,
    required_roles: list[str] | None = None,
    required_permissions: list[str] | None = None,
) -> Any:
    meta = {
        "required_roles": list(required_roles or []),
        "required_permissions": list(required_permissions or []),
    }
    setattr(tool, _META_ATTR, meta)
    return tool


def get_tool_meta(tool: Any) -> dict[str, Any]:
    raw = getattr(tool, _META_ATTR, None)
    if isinstance(raw, dict):
        return {
            "required_roles": list(raw.get("required_roles") or []),
            "required_permissions": list(raw.get("required_permissions") or []),
        }
    return {"required_roles": [], "required_permissions": []}

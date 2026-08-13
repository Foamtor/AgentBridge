"""Build domain catalog snapshot for admin APIs."""

from __future__ import annotations

from typing import Any

from agentbridge_core.protocol.tool_meta import get_tool_meta


def _tool_name(tool: Any) -> str:
    name = getattr(tool, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(tool)


def _tool_details(tools: list[Any]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for tool in tools:
        meta = get_tool_meta(tool)
        details.append(
            {
                "name": _tool_name(tool),
                "description": str(getattr(tool, "description", "") or ""),
                "required_roles": meta["required_roles"],
                "required_permissions": meta["required_permissions"],
                "required_permissions_all": meta["required_permissions_all"],
            }
        )
    return sorted(details, key=lambda item: item["name"])


def _collect_permissions(
    tools: list[Any], *, key: str = "required_permissions"
) -> list[str]:
    perms: set[str] = set()
    for tool in tools:
        meta = get_tool_meta(tool)
        perms.update(meta.get(key) or [])
    return sorted(perms)


def build_domain_catalog(
    *,
    route_names: list[str],
    tools_registry: Any,
    graph_names: set[str],
    meta_map: dict[str, dict[str, Any]],
    approval_actions: Any | None = None,
) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for name in sorted(route_names):
        try:
            raw_tools = tools_registry.get(name)
        except Exception:  # noqa: BLE001 — catalog is best-effort
            raw_tools = []
        if not isinstance(raw_tools, list):
            raw_tools = list(raw_tools) if raw_tools else []
        meta = meta_map.get(name) or {}
        actions = []
        list_for_route = getattr(approval_actions, "list_for_route", None)
        if callable(list_for_route):
            actions = list_for_route(name)
        catalog.append(
            {
                "name": name,
                "description": str(meta.get("description") or ""),
                "routing": dict(meta.get("routing") or {}),
                "tools": sorted(_tool_name(t) for t in raw_tools),
                "required_permissions": _collect_permissions(raw_tools),
                "required_permissions_all": _collect_permissions(
                    raw_tools, key="required_permissions_all"
                ),
                "tool_details": _tool_details(raw_tools),
                "approval_actions": actions,
                "graph_registered": name in graph_names,
            }
        )
    return catalog

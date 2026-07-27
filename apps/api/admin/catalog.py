"""Build domain catalog snapshot for admin APIs."""

from __future__ import annotations

from typing import Any

from agent_base_core.protocol.tool_meta import get_tool_meta


def _tool_name(tool: Any) -> str:
    name = getattr(tool, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(tool)


def _collect_permissions(tools: list[Any]) -> list[str]:
    perms: set[str] = set()
    for tool in tools:
        meta = get_tool_meta(tool)
        perms.update(meta.get("required_permissions") or [])
    return sorted(perms)


def build_domain_catalog(
    *,
    route_names: list[str],
    tools_registry: Any,
    graph_names: set[str],
    meta_map: dict[str, dict[str, Any]],
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
        catalog.append(
            {
                "name": name,
                "description": str(meta.get("description") or ""),
                "tools": sorted(_tool_name(t) for t in raw_tools),
                "required_permissions": _collect_permissions(raw_tools),
                "graph_registered": name in graph_names,
            }
        )
    return catalog

"""Allowlist DataFilter — no rules means no rows."""

from __future__ import annotations

from typing import Any

from agent_base_core.protocol.context import RunContext


class AllowlistDataFilter:
    """Keep only declared fields; empty rules → deny-all (``[]``)."""

    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        # Each rule: {"fields": ["id", "status"]}
        self.rules = list(rules or [])

    def apply(self, rows: list[dict[str, Any]], ctx: RunContext) -> list[dict[str, Any]]:
        _ = ctx
        if not self.rules:
            return []
        allowed: set[str] = set()
        for rule in self.rules:
            for f in rule.get("fields") or []:
                allowed.add(str(f))
        if not allowed:
            return []
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append({k: v for k, v in row.items() if k in allowed})
        return out

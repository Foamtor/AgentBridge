"""In-memory FakeDataSource for tests (seeded rows + last call capture)."""

from __future__ import annotations

import re
from typing import Any


class FakeDataSource:
    """Minimal fake: matches simple ``FROM <table>`` and optional equality filters."""

    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self.last_sql: str | None = None
        self.last_params: tuple[Any, ...] = ()

    def seed(self, table: str, rows: list[dict[str, Any]]) -> None:
        self._tables[table] = [dict(r) for r in rows]

    async def query(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        self.last_sql = sql
        self.last_params = params
        table = _table_from_sql(sql)
        rows = list(self._tables.get(table, []))
        # Apply positional params in order of ``col = $N`` / ``col = ?`` appearances.
        filters = _equality_filters(sql)
        for i, col in enumerate(filters):
            if i >= len(params):
                break
            want = params[i]
            rows = [r for r in rows if r.get(col) == want]
        return [dict(r) for r in rows]

    async def execute(self, sql: str, *params: Any) -> int:
        self.last_sql = sql
        self.last_params = params
        return 0

    async def close(self) -> None:
        return None


_FROM_RE = re.compile(r"\bFROM\s+([a-zA-Z_][\w]*)", re.IGNORECASE)
_EQ_RE = re.compile(
    r"\b([a-zA-Z_][\w]*)\s*=\s*(?:\$\d+|\?)",
    re.IGNORECASE,
)


def _table_from_sql(sql: str) -> str:
    m = _FROM_RE.search(sql)
    if not m:
        return ""
    return m.group(1)


def _equality_filters(sql: str) -> list[str]:
    return [m.group(1) for m in _EQ_RE.finditer(sql)]

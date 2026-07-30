"""In-memory FakeDataSource for tests (seeded rows + last call capture)."""

from __future__ import annotations

import copy
import re
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from agentbridge_core.ports.data_source import DataSource

T = TypeVar("T")


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
        # PostgreSQL ``$N`` placeholders refer to the Nth argument, independent
        # of their appearance order. ``?`` placeholders remain appearance-based.
        filters = _equality_filters(sql)
        for col, parameter_index in filters:
            if parameter_index >= len(params):
                break
            want = params[parameter_index]
            rows = [r for r in rows if r.get(col) == want]
        return [dict(r) for r in rows]

    async def execute(self, sql: str, *params: Any) -> int:
        self.last_sql = sql
        self.last_params = params
        insert = _insert_parts(sql)
        if insert is not None:
            table, columns, parameter_indexes = insert
            if len(columns) != len(params):
                raise ValueError("INSERT parameter count does not match columns")
            if any(index >= len(params) for index in parameter_indexes):
                raise ValueError("INSERT placeholder index exceeds parameter count")
            row = {
                column: params[parameter_index]
                for column, parameter_index in zip(columns, parameter_indexes)
            }
            self._tables.setdefault(table, []).append(row)
            return 1
        return 0

    async def transaction(self, operation: Callable[[DataSource], Awaitable[T]]) -> T:
        snapshot = copy.deepcopy(self._tables)
        try:
            return await operation(self)
        except BaseException:
            self._tables = snapshot
            raise

    async def close(self) -> None:
        return None


_FROM_RE = re.compile(r"\bFROM\s+([a-zA-Z_][\w]*)", re.IGNORECASE)
_EQ_RE = re.compile(
    r"\b([a-zA-Z_][\w]*)\s*=\s*(\$(\d+)|\?)",
    re.IGNORECASE,
)
_INSERT_RE = re.compile(
    r"^\s*INSERT\s+INTO\s+([a-zA-Z_][\w]*)\s*\(([^)]+)\)\s*"
    r"VALUES\s*\(([^)]+)\)\s*;?\s*$",
    re.IGNORECASE,
)


def _table_from_sql(sql: str) -> str:
    m = _FROM_RE.search(sql)
    if not m:
        return ""
    return m.group(1)


def _equality_filters(sql: str) -> list[tuple[str, int]]:
    question_index = 0
    filters: list[tuple[str, int]] = []
    for match in _EQ_RE.finditer(sql):
        ordinal = match.group(3)
        if ordinal is not None:
            parameter_index = int(ordinal) - 1
            if parameter_index < 0:
                raise ValueError("Query placeholders start at $1")
        else:
            parameter_index = question_index
            question_index += 1
        filters.append((match.group(1), parameter_index))
    return filters


def _insert_parts(sql: str) -> tuple[str, list[str], list[int]] | None:
    match = _INSERT_RE.match(sql)
    if match is None:
        return None
    values = [value.strip() for value in match.group(3).split(",")]
    if any(not re.fullmatch(r"\$(\d+)|\?", value) for value in values):
        raise ValueError("FakeDataSource INSERT values must be bound parameters")
    if all(value == "?" for value in values):
        parameter_indexes = list(range(len(values)))
    elif all(value.startswith("$") for value in values):
        parameter_indexes = [int(value[1:]) - 1 for value in values]
        if any(index < 0 for index in parameter_indexes):
            raise ValueError("INSERT placeholders start at $1")
    else:
        raise ValueError("FakeDataSource INSERT cannot mix $N and ? placeholders")
    columns = [column.strip() for column in match.group(2).split(",")]
    return match.group(1), columns, parameter_indexes

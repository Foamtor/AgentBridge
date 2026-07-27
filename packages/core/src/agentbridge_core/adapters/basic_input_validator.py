"""Basic query length + NUL strip validator."""

from __future__ import annotations


class BasicInputValidator:
    def __init__(self, max_len: int = 8000) -> None:
        self.max_len = max_len

    def validate_query(self, query: str) -> str:
        if len(query) > self.max_len:
            raise ValueError("query too long")
        return query.replace("\x00", "")

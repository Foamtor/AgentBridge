"""No-op run hooks."""

from __future__ import annotations

from typing import Any


class NoopHooks:
    async def on_run_end(self, payload: dict[str, Any]) -> None:
        return None

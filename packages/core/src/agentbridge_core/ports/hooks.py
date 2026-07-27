"""Protocol: RunHooks."""

from __future__ import annotations

from typing import Any, Protocol


class RunHooks(Protocol):
    async def on_run_end(self, payload: dict[str, Any]) -> None: ...

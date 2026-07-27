"""Protocol: CheckpointerFactory."""

from __future__ import annotations

from typing import Any, Protocol


class CheckpointerFactory(Protocol):
    async def setup(self) -> None: ...

    async def get(self) -> Any: ...

    async def teardown(self) -> None: ...

    def is_setup(self) -> bool:
        """True after successful setup(); used by /ready."""
        ...

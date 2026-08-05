"""Ports for host-owned console authentication persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class ConsoleAuthStore(Protocol):
    async def get_admin(self, username: str) -> dict[str, Any] | None: ...

    async def create_admin(
        self, username: str, password_hash: str, *, must_change_password: bool
    ) -> bool: ...

    async def update_admin_password(
        self, username: str, password_hash: str, *, must_change_password: bool,
        initial_password_issued_at: datetime | None = None
    ) -> None: ...

    async def create_session(
        self,
        session_hash: str,
        username: str,
        kind: str,
        *,
        created_at: datetime,
        expires_at: datetime,
    ) -> None: ...

    async def get_session(self, session_hash: str) -> dict[str, Any] | None: ...

    async def touch_session(
        self, session_hash: str, *, last_seen_at: datetime, expires_at: datetime
    ) -> None: ...

    async def revoke_session(self, session_hash: str, *, revoked_at: datetime) -> None: ...

    async def revoke_all_sessions(self, username: str, *, revoked_at: datetime) -> None: ...

    async def get_login_failures(self, bucket_key: str) -> dict[str, Any] | None: ...

    async def record_login_failure(self, bucket_key: str, *, now: datetime) -> None: ...

    async def clear_login_failures(self, bucket_key: str) -> None: ...

"""In-memory console auth store for API tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class FakeConsoleAuthStore:
    def __init__(self) -> None:
        self.admins: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.attempts: dict[str, dict[str, Any]] = {}

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def ttl(self) -> timedelta:
        return timedelta(hours=12)

    async def get_admin(self, username: str) -> dict[str, Any] | None:
        row = self.admins.get(username)
        return dict(row) if row else None

    async def create_admin(
        self, username: str, password_hash: str, *, must_change_password: bool
    ) -> bool:
        if username in self.admins:
            return False
        self.admins[username] = {
            "username": username,
            "password_hash": password_hash,
            "must_change_password": must_change_password,
            "created_at": self.now(),
            "initial_password_issued_at": self.now(),
            "password_changed_at": None,
        }
        return True

    async def update_admin_password(
        self, username: str, password_hash: str, *, must_change_password: bool,
        initial_password_issued_at: datetime | None = None
    ) -> None:
        self.admins[username]["password_hash"] = password_hash
        self.admins[username]["must_change_password"] = must_change_password
        self.admins[username]["initial_password_issued_at"] = initial_password_issued_at
        self.admins[username]["password_changed_at"] = None if must_change_password else self.now()

    async def create_session(
        self,
        session_hash: str,
        username: str,
        kind: str,
        *,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        self.sessions[session_hash] = {
            "session_hash": session_hash,
            "username": username,
            "kind": kind,
            "created_at": created_at,
            "last_seen_at": created_at,
            "expires_at": expires_at,
            "revoked_at": None,
        }

    async def get_session(self, session_hash: str) -> dict[str, Any] | None:
        row = self.sessions.get(session_hash)
        return dict(row) if row else None

    async def touch_session(
        self, session_hash: str, *, last_seen_at: datetime, expires_at: datetime
    ) -> None:
        if session_hash in self.sessions:
            self.sessions[session_hash]["last_seen_at"] = last_seen_at
            self.sessions[session_hash]["expires_at"] = expires_at

    async def revoke_session(self, session_hash: str, *, revoked_at: datetime) -> None:
        if session_hash in self.sessions:
            self.sessions[session_hash]["revoked_at"] = revoked_at

    async def revoke_all_sessions(self, username: str, *, revoked_at: datetime) -> None:
        for row in self.sessions.values():
            if row["username"] == username:
                row["revoked_at"] = revoked_at

    async def get_login_failures(self, bucket_key: str) -> dict[str, Any] | None:
        row = self.attempts.get(bucket_key)
        return dict(row) if row else None

    async def record_login_failure(self, bucket_key: str, *, now: datetime) -> None:
        row = self.attempts.setdefault(
            bucket_key, {"bucket_key": bucket_key, "failures": 0, "first_failure_at": now}
        )
        row["failures"] += 1
        row["last_failure_at"] = now

    async def clear_login_failures(self, bucket_key: str) -> None:
        self.attempts.pop(bucket_key, None)

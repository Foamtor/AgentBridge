"""Host-owned local administrator service.

The service depends on ``ConsoleAuthStore`` only. Persistence adapters are
created by the API composition root and injected by callers.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from auth.ports import ConsoleAuthStore


class PasswordPolicyError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AuthSessionError(ValueError):
    pass


@dataclass(frozen=True)
class BootstrapCredentials:
    username: str
    initial_password: str


@dataclass(frozen=True)
class AuthSession:
    token: str
    username: str
    kind: str
    expires_at: datetime


class ConsoleAdminService:
    def __init__(
        self,
        store: ConsoleAuthStore,
        *,
        session_idle_seconds: int = 43200,
        session_absolute_seconds: int = 86400,
        password_change_seconds: int = 900,
        password_min_length: int = 8,
        password_max_length: int = 128,
        login_failure_window_seconds: int = 300,
        initial_password_ttl_seconds: int = 86400,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self.store = store
        self.session_idle_seconds = session_idle_seconds
        self.session_absolute_seconds = session_absolute_seconds
        self.password_change_seconds = password_change_seconds
        self.password_min_length = password_min_length
        self.password_max_length = password_max_length
        self.login_failure_window_seconds = login_failure_window_seconds
        self.initial_password_ttl_seconds = initial_password_ttl_seconds
        self.hasher = password_hasher or PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)

    async def ensure_admin(self, *, username: str = "admin") -> BootstrapCredentials | None:
        if await self.store.get_admin(username) is not None:
            return None
        initial_password = secrets.token_urlsafe(24)
        created = await self.store.create_admin(
            username,
            self.hasher.hash(initial_password),
            must_change_password=True,
        )
        return BootstrapCredentials(username, initial_password) if created else None

    def validate_new_password(
        self,
        candidate: str,
        *,
        username: str = "admin",
        current_hash: str | None = None,
    ) -> None:
        length = len(candidate)
        if length < self.password_min_length:
            raise PasswordPolicyError("password_too_short")
        if length > self.password_max_length:
            raise PasswordPolicyError("password_too_long")
        if not any(c.isalpha() for c in candidate) or not any(c.isdigit() for c in candidate):
            raise PasswordPolicyError("password_too_weak")

    def hash_password(self, password: str) -> str:
        return self.hasher.hash(password)

    def verify_password(self, password_hash: str, password: str) -> bool:
        try:
            return bool(self.hasher.verify(password_hash, password))
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    @staticmethod
    def hash_session(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def create_session(
        self,
        username: str,
        *,
        kind: str,
        now: datetime | None = None,
    ) -> str:
        now = now or datetime.now(timezone.utc)
        duration = (
            self.password_change_seconds
            if kind == "password_change"
            else self.session_absolute_seconds
        )
        token = secrets.token_urlsafe(32)
        await self.store.create_session(
            self.hash_session(token),
            username,
            kind,
            created_at=now,
            expires_at=now + timedelta(seconds=duration),
        )
        return token

    async def authenticate(
        self, username: str, password: str, *, bucket_key: str
    ) -> AuthSession:
        now = datetime.now(timezone.utc)
        failures = await self.store.get_login_failures(bucket_key)
        if failures and int(failures.get("failures") or 0) >= 5:
            first_failure = failures.get("first_failure_at") or failures.get("last_failure_at")
            if isinstance(first_failure, datetime) and first_failure.tzinfo is None:
                first_failure = first_failure.replace(tzinfo=timezone.utc)
            if isinstance(first_failure, datetime) and (now - first_failure).total_seconds() < self.login_failure_window_seconds:
                raise AuthSessionError("auth_rate_limited")
            await self.store.clear_login_failures(bucket_key)
        admin = await self.store.get_admin(username)
        issued_at = admin.get("initial_password_issued_at") if admin else None
        if admin and admin.get("must_change_password") and isinstance(issued_at, datetime):
            issued_at = issued_at if issued_at.tzinfo else issued_at.replace(tzinfo=timezone.utc)
            if (now - issued_at).total_seconds() >= self.initial_password_ttl_seconds:
                await self.store.record_login_failure(bucket_key, now=now)
                raise AuthSessionError("auth_initial_password_expired")
        if admin is None or not self.verify_password(admin["password_hash"], password):
            await self.store.record_login_failure(bucket_key, now=now)
            raise AuthSessionError("auth_invalid_credentials")
        await self.store.clear_login_failures(bucket_key)
        kind = "password_change" if admin.get("must_change_password") else "authenticated"
        token = await self.create_session(username, kind=kind)
        session = await self.get_session(token)
        assert session is not None
        return AuthSession(token, username, kind, session["expires_at"])

    async def logout(self, token: str) -> None:
        await self.store.revoke_session(
            self.hash_session(token), revoked_at=datetime.now(timezone.utc)
        )

    async def rotate_initial_password(self, *, username: str = "admin") -> str:
        admin = await self.store.get_admin(username)
        if admin is None:
            raise AuthSessionError("admin_not_found")
        password = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        await self.store.update_admin_password(
            username, self.hash_password(password), must_change_password=True,
            initial_password_issued_at=now,
        )
        await self.store.revoke_all_sessions(username, revoked_at=now)
        return password

    async def get_session(self, token: str, *, now: datetime | None = None) -> dict[str, Any] | None:
        now = now or datetime.now(timezone.utc)
        record = await self.store.get_session(self.hash_session(token))
        if not record or record.get("revoked_at") is not None:
            return None
        expires_at = record.get("expires_at")
        if expires_at is None or expires_at <= now:
            return None
        idle_limit = record.get("last_seen_at", now) + timedelta(seconds=self.session_idle_seconds)
        if idle_limit <= now:
            return None
        # The forced password-change session is deliberately short-lived and
        # must not be extended by ordinary session refreshes.
        if record.get("kind") != "authenticated":
            return record
        created_at = record.get("created_at", now)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        absolute_limit = created_at + timedelta(seconds=self.session_absolute_seconds)
        refreshed_expires_at = min(absolute_limit, now + timedelta(seconds=self.session_idle_seconds))
        if record.get("last_seen_at") != now or record.get("expires_at") != refreshed_expires_at:
            await self.store.touch_session(
                self.hash_session(token), last_seen_at=now, expires_at=refreshed_expires_at
            )
            record["last_seen_at"] = now
            record["expires_at"] = refreshed_expires_at
        return record

    async def change_password(
        self,
        *,
        session_token: str,
        current_password: str,
        new_password: str,
    ) -> AuthSession:
        record = await self.get_session(session_token)
        if not record or record.get("kind") not in {"password_change", "authenticated"}:
            raise AuthSessionError("invalid_session")
        username = str(record["username"])
        admin = await self.store.get_admin(username)
        if not admin or not self.verify_password(admin["password_hash"], current_password):
            raise AuthSessionError("auth_invalid_credentials")
        self.validate_new_password(
            new_password,
            username=username,
            current_hash=admin["password_hash"],
        )
        now = datetime.now(timezone.utc)
        await self.store.update_admin_password(
            username,
            self.hash_password(new_password),
            must_change_password=False,
            initial_password_issued_at=None,
        )
        await self.store.revoke_all_sessions(username, revoked_at=now)
        token = await self.create_session(username, kind="authenticated", now=now)
        fresh = await self.store.get_session(self.hash_session(token))
        assert fresh is not None
        return AuthSession(token, username, "authenticated", fresh["expires_at"])

    async def verify_reauthentication(
        self, *, session_token: str, password: str
    ) -> str:
        """Verify an active admin session's password without issuing a session."""
        record = await self.get_session(session_token)
        if not record or record.get("kind") != "authenticated":
            raise AuthSessionError("invalid_session")
        bucket_key = f"reauth:{self.hash_session(session_token)}"
        now = datetime.now(timezone.utc)
        failures = await self.store.get_login_failures(bucket_key)
        if failures and int(failures.get("failures") or 0) >= 5:
            first_failure = failures.get("first_failure_at") or failures.get("last_failure_at")
            if isinstance(first_failure, datetime) and first_failure.tzinfo is None:
                first_failure = first_failure.replace(tzinfo=timezone.utc)
            if isinstance(first_failure, datetime) and (now - first_failure).total_seconds() < self.login_failure_window_seconds:
                raise AuthSessionError("auth_rate_limited")
            await self.store.clear_login_failures(bucket_key)
        username = str(record["username"])
        admin = await self.store.get_admin(username)
        if admin is None or not self.verify_password(admin["password_hash"], password):
            await self.store.record_login_failure(bucket_key, now=now)
            raise AuthSessionError("reauth_invalid_credentials")
        await self.store.clear_login_failures(bucket_key)
        return username

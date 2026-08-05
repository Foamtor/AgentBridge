from datetime import datetime, timedelta, timezone

import pytest

from auth.local_admin import ConsoleAdminService, PasswordPolicyError
from testing.fake_console_auth import FakeConsoleAuthStore


@pytest.fixture
def service():
    return ConsoleAdminService(FakeConsoleAuthStore())


@pytest.mark.asyncio
async def test_ensure_admin_generates_once(service):
    first = await service.ensure_admin()
    second = await service.ensure_admin()

    assert first is not None
    assert len(first.initial_password) >= 24
    assert second is None
    record = await service.store.get_admin("admin")
    assert record is not None
    assert record["password_hash"] != first.initial_password
    assert record["must_change_password"] is True


@pytest.mark.asyncio
async def test_password_policy_requires_eight_characters_with_letters_and_digits(service):
    with pytest.raises(PasswordPolicyError) as exc:
        service.validate_new_password("short", username="admin")
    assert exc.value.code == "password_too_short"

    with pytest.raises(PasswordPolicyError) as exc:
        service.validate_new_password("abcdefgh", username="admin")
    assert exc.value.code == "password_too_weak"

    with pytest.raises(PasswordPolicyError) as exc:
        service.validate_new_password("12345678", username="admin")
    assert exc.value.code == "password_too_weak"

    service.validate_new_password("admin123", username="admin")


@pytest.mark.asyncio
async def test_change_password_hashes_and_rotates_sessions(service):
    created = await service.ensure_admin()
    assert created is not None
    old = await service.create_session("admin", kind="password_change")
    changed = await service.change_password(
        session_token=old,
        current_password=created.initial_password,
        new_password="Correct Horse Battery Staple 2026!",
    )

    assert changed.kind == "authenticated"
    old_record = await service.store.get_session(service.hash_session(old))
    assert old_record is not None and old_record["revoked_at"] is not None
    record = await service.store.get_admin("admin")
    assert record is not None and record["must_change_password"] is False
    assert service.verify_password(record["password_hash"], "Correct Horse Battery Staple 2026!")


@pytest.mark.asyncio
async def test_session_store_only_receives_hash(service):
    await service.ensure_admin()
    token = await service.create_session("admin", kind="authenticated")
    assert token
    assert len(token) > 32
    assert await service.store.get_session(service.hash_session(token)) is not None
    assert await service.store.get_session(token) is None


@pytest.mark.asyncio
async def test_expired_session_is_not_authenticated(service):
    await service.ensure_admin()
    token = await service.create_session(
        "admin", kind="authenticated", now=datetime.now(timezone.utc) - timedelta(days=2)
    )
    assert await service.get_session(token) is None


@pytest.mark.asyncio
async def test_active_session_refreshes_idle_expiry_without_exceeding_absolute_limit(service):
    await service.ensure_admin()
    created_at = datetime.now(timezone.utc) - timedelta(hours=11)
    token = await service.create_session("admin", kind="authenticated", now=created_at)
    checked_at = created_at + timedelta(hours=11, minutes=30)

    session = await service.get_session(token, now=checked_at)

    assert session is not None
    assert session["last_seen_at"] == checked_at
    expected = min(
        created_at + timedelta(seconds=service.session_absolute_seconds),
        checked_at + timedelta(seconds=service.session_idle_seconds),
    )
    assert session["expires_at"] == expected


@pytest.mark.asyncio
async def test_initial_password_expires_before_first_change(service):
    created = await service.ensure_admin()
    assert created is not None
    service.store.admins["admin"]["initial_password_issued_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=service.initial_password_ttl_seconds + 1)
    )

    with pytest.raises(ValueError, match="auth_initial_password_expired"):
        await service.authenticate("admin", created.initial_password, bucket_key="test-client:admin")


@pytest.mark.asyncio
async def test_login_failure_limit_expires_after_window(service):
    created = await service.ensure_admin()
    assert created is not None
    for _ in range(5):
        with pytest.raises(ValueError, match="auth_invalid_credentials"):
            await service.authenticate("admin", "wrong", bucket_key="test-client:admin")
    with pytest.raises(ValueError, match="auth_rate_limited"):
        await service.authenticate("admin", created.initial_password, bucket_key="test-client:admin")

    attempts = service.store.attempts["test-client:admin"]
    expired = datetime.now(timezone.utc) - timedelta(seconds=service.login_failure_window_seconds + 1)
    attempts["first_failure_at"] = expired
    attempts["last_failure_at"] = expired
    session = await service.authenticate("admin", created.initial_password, bucket_key="test-client:admin")
    assert session.kind == "password_change"

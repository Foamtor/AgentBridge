import pytest

from testing.fake_console_auth import FakeConsoleAuthStore


@pytest.mark.asyncio
async def test_fake_store_admin_session_and_attempt_contract():
    store = FakeConsoleAuthStore()
    await store.create_admin(
        "admin", "hash", must_change_password=True
    )
    assert (await store.get_admin("admin"))["username"] == "admin"
    await store.create_session(
        "hash-token",
        "admin",
        "authenticated",
        created_at=store.now(),
        expires_at=store.now() + store.ttl(),
    )
    session = await store.get_session("hash-token")
    assert session["kind"] == "authenticated"
    await store.record_login_failure("ip:admin", now=store.now())
    await store.record_login_failure("ip:admin", now=store.now())
    assert (await store.get_login_failures("ip:admin"))["failures"] == 2
    await store.clear_login_failures("ip:admin")
    assert await store.get_login_failures("ip:admin") is None

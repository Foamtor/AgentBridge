"""claims_to_run_context unit tests."""

from __future__ import annotations

from auth.run_context import claims_to_run_context


def test_auth_off_uses_dev_admin_defaults() -> None:
    ctx = claims_to_run_context(None, auth_required=False)
    assert ctx.user_id == "dev"
    assert ctx.tenant_id == "dev"
    assert ctx.roles == ["admin"]
    assert ctx.permissions == ["*"]


def test_auth_on_maps_jwt_claims() -> None:
    ctx = claims_to_run_context(
        {
            "sub": "u-42",
            "tenant_id": "acme",
            "roles": ["viewer"],
            "permissions": ["read"],
        },
        auth_required=True,
    )
    assert ctx.user_id == "u-42"
    assert ctx.tenant_id == "acme"
    assert ctx.roles == ["viewer"]
    assert ctx.permissions == ["read"]


def test_auth_on_accepts_tid_and_perms_aliases() -> None:
    ctx = claims_to_run_context(
        {"sub": "u1", "tid": "t9", "roles": "admin", "perms": "write"},
        auth_required=True,
    )
    assert ctx.tenant_id == "t9"
    assert ctx.roles == ["admin"]
    assert ctx.permissions == ["write"]


def test_auth_on_missing_claims_is_empty_not_admin() -> None:
    ctx = claims_to_run_context(None, auth_required=True)
    assert ctx.user_id == ""
    assert ctx.tenant_id == ""
    assert ctx.roles == []
    assert ctx.permissions == []

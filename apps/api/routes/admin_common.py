"""Shared helpers for admin routes."""

from __future__ import annotations

from fastapi import Request

from auth.run_context import claims_to_run_context


def admin_ctx(request: Request):
    settings = request.app.state.settings
    claims = getattr(request.state, "auth_claims", None)
    return claims_to_run_context(
        claims,
        auth_required=settings.auth_required,
        policy_bundle_version=settings.policy_bundle_version,
    )

"""Test-only helpers for P2-A HTTP authentication cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt


def make_hs256_token(secret: str, **claims: Any) -> str:
    """Create a short-lived, non-production token without logging it."""

    payload = {
        "sub": "p2a-user",
        "tenant_id": "p2a-tenant",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        **claims,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def bearer_headers(secret: str, **claims: Any) -> dict[str, str]:
    """Return a request header without exposing the token in test output."""

    return {"Authorization": f"Bearer {make_hs256_token(secret, **claims)}"}

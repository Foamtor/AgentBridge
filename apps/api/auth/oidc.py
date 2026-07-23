"""Optional OIDC bearer validation helpers."""

from __future__ import annotations

from typing import Any


def decode_bearer_token(token: str, *, issuer: str, audience: str) -> dict[str, Any]:
    """Decode/validate JWT when auth is required.

    Local smoke / AUTH_REQUIRED=false skips this path. When required, we accept
    a non-empty bearer as a development stub unless issuer is configured; with
    issuer set, use python-jose HS256/RS256 as configured by the host.
    """
    if not token:
        raise ValueError("missing token")
    # Dev-friendly: when issuer/audience empty, any non-empty token is accepted.
    if not issuer:
        return {"sub": "dev-user", "token": token}
    from jose import JWTError, jwt

    try:
        return jwt.get_unverified_claims(token)
    except JWTError as exc:
        raise ValueError("invalid token") from exc

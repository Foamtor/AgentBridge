"""OIDC / Bearer JWT validation."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from jose import JWTError, jwt


class AuthConfigError(ValueError):
    """Raised when auth is required but the host is misconfigured."""


def validate_auth_settings(
    *,
    auth_required: bool,
    auth_dev_stub: bool,
    oidc_issuer: str,
    oidc_jwt_secret: str,
) -> None:
    if not auth_required:
        return
    if auth_dev_stub:
        return
    if not oidc_issuer and not oidc_jwt_secret:
        raise AuthConfigError(
            "AUTH_REQUIRED=true needs OIDC_ISSUER (JWKS) or OIDC_JWT_SECRET, "
            "or set AUTH_DEV_STUB=1 for local stub only"
        )


@lru_cache(maxsize=8)
def _openid_config(issuer: str) -> dict[str, Any]:
    base = issuer.rstrip("/") + "/"
    url = base + ".well-known/openid-configuration"
    with httpx.Client(timeout=10.0) as client:
        # Authentik and many IdPs expose discovery under the issuer root.
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            # Fallback: issuer already includes application path; try parent-style jwks later.
            return {}


@lru_cache(maxsize=8)
def _jwks(issuer: str) -> dict[str, Any]:
    cfg = _openid_config(issuer)
    jwks_uri = cfg.get("jwks_uri")
    if not jwks_uri:
        jwks_uri = issuer.rstrip("/") + "/jwks/"
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(jwks_uri)
        resp.raise_for_status()
        return resp.json()


def _rsa_key_for_token(token: str, jwks: dict[str, Any]) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    for key in jwks.get("keys", []):
        if kid is None or key.get("kid") == kid:
            return key
    raise ValueError("no matching JWK")


def decode_bearer_token(
    token: str,
    *,
    issuer: str = "",
    audience: str = "",
    jwt_secret: str = "",
    auth_dev_stub: bool = False,
) -> dict[str, Any]:
    """Validate Bearer JWT.

    - AUTH_DEV_STUB=1: accept any non-empty token (local only).
    - OIDC_JWT_SECRET: HS256 verify (tests / simple deployments).
    - OIDC_ISSUER: fetch JWKS and verify RS256 (or header alg).
    """
    if not token:
        raise ValueError("missing token")
    if auth_dev_stub:
        return {"sub": "dev-user", "token": token}

    options = {
        "verify_aud": bool(audience),
        "verify_iss": bool(issuer),
    }
    decode_kwargs: dict[str, Any] = {"options": options}
    if audience:
        decode_kwargs["audience"] = audience
    if issuer:
        decode_kwargs["issuer"] = issuer.rstrip("/")

    try:
        if jwt_secret:
            return jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                **decode_kwargs,
            )
        if not issuer:
            raise ValueError("issuer or jwt_secret required when auth stub is off")
        jwks = _jwks(issuer)
        key = _rsa_key_for_token(token, jwks)
        alg = jwt.get_unverified_header(token).get("alg") or "RS256"
        return jwt.decode(token, key, algorithms=[alg], **decode_kwargs)
    except JWTError as exc:
        raise ValueError("invalid token") from exc

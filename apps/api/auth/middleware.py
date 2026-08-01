"""Optional bearer auth middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from auth.oidc import decode_bearer_token


def has_required_identity(claims: dict[str, object]) -> bool:
    """Require stable actor and tenant identity before routes see a token."""

    subject = claims.get("sub")
    tenant = claims.get("tenant_id") or claims.get("tid")
    return (
        isinstance(subject, str)
        and bool(subject.strip())
        and isinstance(tenant, str)
        and bool(tenant.strip())
    )


class OptionalOidcMiddleware(BaseHTTPMiddleware):
    """When settings.auth_required is True, require Authorization: Bearer."""

    def __init__(
        self,
        app,
        *,
        auth_required: bool,
        issuer: str = "",
        audience: str = "",
        jwt_secret: str = "",
        auth_dev_stub: bool = False,
    ):
        super().__init__(app)
        self.auth_required = auth_required
        self.issuer = issuer
        self.audience = audience
        self.jwt_secret = jwt_secret
        self.auth_dev_stub = auth_dev_stub

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in {"/health", "/ready", "/metrics"} or path.startswith(
            ("/docs", "/openapi")
        ):
            return await call_next(request)

        if not self.auth_required:
            return await call_next(request)

        header = request.headers.get("authorization") or ""
        if not header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": {
                        "code": "unauthorized",
                        "message": "missing bearer token",
                    }
                },
            )
        token = header.split(" ", 1)[1].strip()
        try:
            claims = decode_bearer_token(
                token,
                issuer=self.issuer,
                audience=self.audience,
                jwt_secret=self.jwt_secret,
                auth_dev_stub=self.auth_dev_stub,
            )
        except ValueError:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": {
                        "code": "unauthorized",
                        "message": "invalid bearer token",
                    }
                },
            )
        if not has_required_identity(claims):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": {
                        "code": "unauthorized",
                        "message": "invalid bearer token",
                    }
                },
            )
        request.state.auth_claims = claims
        return await call_next(request)

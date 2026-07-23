"""Optional bearer auth middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from auth.oidc import decode_bearer_token


class OptionalOidcMiddleware(BaseHTTPMiddleware):
    """When settings.auth_required is True, require Authorization: Bearer."""

    def __init__(self, app, *, auth_required: bool, issuer: str = "", audience: str = ""):
        super().__init__(app)
        self.auth_required = auth_required
        self.issuer = issuer
        self.audience = audience

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path == "/health" or path.startswith("/docs") or path.startswith("/openapi"):
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
                token, issuer=self.issuer, audience=self.audience
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
        request.state.auth_claims = claims
        return await call_next(request)

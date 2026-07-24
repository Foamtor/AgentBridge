"""FastAPI create_app() entry."""

from __future__ import annotations

from fastapi import FastAPI

from auth.middleware import OptionalOidcMiddleware
from auth.oidc import validate_auth_settings
from config.settings import get_settings
from lifespan import lifespan
from routes.chat import router as chat_router
from routes.health import router as health_router


def create_app() -> FastAPI:
    settings = get_settings()
    validate_auth_settings(
        auth_required=settings.auth_required,
        auth_dev_stub=settings.auth_dev_stub,
        oidc_issuer=settings.oidc_issuer,
        oidc_jwt_secret=settings.oidc_jwt_secret,
    )
    app = FastAPI(title="agent-base-api", lifespan=lifespan)
    app.add_middleware(
        OptionalOidcMiddleware,
        auth_required=settings.auth_required,
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        jwt_secret=settings.oidc_jwt_secret,
        auth_dev_stub=settings.auth_dev_stub,
    )
    app.include_router(health_router)
    app.include_router(chat_router)
    return app


app = create_app()

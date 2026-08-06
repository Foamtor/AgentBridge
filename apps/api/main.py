"""FastAPI create_app() entry."""

from __future__ import annotations

from fastapi import FastAPI

from auth.middleware import OptionalOidcMiddleware
from auth.oidc import validate_auth_settings
from config.settings import get_settings
from lifespan import _build_redis, lifespan
from middleware.rate_limit import RateLimitMiddleware
from routes.admin import router as admin_router
from routes.admin_config import router as admin_config_router
from routes.admin_overview import router as admin_overview_router
from routes.admin_runs import router as admin_runs_router
from routes.admin_config_write import router as admin_config_write_router
from routes.admin_tools import router as admin_tools_router
from routes.admin_knowledge import router as admin_knowledge_router
from routes.admin_usage import router as admin_usage_router
from routes.ingest import router as ingest_router
from routes.prompts import router as prompts_router
from routes.approvals import router as approvals_router
from routes.auth import router as auth_router
from routes.console import router as console_router
from routes.chat import router as chat_router
from routes.health import router as health_router
from routes.metrics import router as metrics_router
from routes.models import router as models_router
from routes.ready import router as ready_router
from routes.runs import router as runs_router
from routes.threads import router as threads_router


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_auth_mode()
    if settings.resolved_auth_mode == "oidc":
        validate_auth_settings(
            auth_required=settings.auth_required,
            auth_dev_stub=settings.auth_dev_stub,
            oidc_issuer=settings.oidc_issuer,
            oidc_jwt_secret=settings.oidc_jwt_secret,
        )
    redis_client = None
    if settings.lock_backend == "redis" or settings.rate_limit_backend == "redis":
        redis_client = _build_redis(settings)
    app = FastAPI(title="agentbridge-api", lifespan=lifespan)
    app.state.bootstrap_redis = redis_client
    # Last added = outermost. Rate limit wraps auth so 429 can fire before JWT work.
    app.add_middleware(
        OptionalOidcMiddleware,
        auth_required=settings.auth_required,
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        jwt_secret=settings.oidc_jwt_secret,
        auth_dev_stub=settings.auth_dev_stub,
        auth_mode=settings.resolved_auth_mode,
    )
    app.add_middleware(
        RateLimitMiddleware,
        limit_per_minute=settings.rate_limit_per_minute,
        redis=redis_client if settings.rate_limit_backend == "redis" else None,
    )
    app.include_router(health_router)
    app.include_router(ready_router)
    app.include_router(auth_router)
    app.include_router(console_router)
    app.include_router(metrics_router)
    app.include_router(models_router)
    app.include_router(chat_router)
    app.include_router(approvals_router)
    app.include_router(admin_router)
    app.include_router(admin_overview_router)
    app.include_router(admin_config_router)
    app.include_router(admin_tools_router)
    app.include_router(admin_runs_router)
    app.include_router(admin_config_write_router)
    app.include_router(prompts_router)
    app.include_router(ingest_router)
    app.include_router(admin_usage_router)
    app.include_router(admin_knowledge_router)
    app.include_router(threads_router)
    app.include_router(runs_router)
    return app


app = create_app()

"""FastAPI create_app() entry."""

from __future__ import annotations

from fastapi import FastAPI

from lifespan import lifespan
from routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="agent-base-api", lifespan=lifespan)
    app.include_router(health_router)
    return app


app = create_app()

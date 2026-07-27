"""FastAPI application factory.

Wires configuration, logging, the DI container lifecycle, security middleware,
exception handlers, and routers. Import ``app`` for ASGI servers
(``uvicorn app.main:app``) or call :func:`create_app` in tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth, health, notes, tasks, webhook
from app.config.settings import get_settings
from app.core.container import container
from app.core.handlers import register_exception_handlers
from app.middleware.context import RequestContextMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await container.startup()
    try:
        yield
    finally:
        await container.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app.name,
        version="0.1.0",
        docs_url="/docs" if not settings.app.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Middleware (outermost first).
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Routers.
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(webhook.router)
    app.include_router(tasks.router)
    app.include_router(notes.router)

    return app


app = create_app()

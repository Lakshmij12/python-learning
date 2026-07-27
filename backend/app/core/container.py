"""Lightweight dependency-injection container.

Rather than pull in a heavy DI framework, we use a small, explicit container
that owns process-wide singletons (settings, async DB engine/session factory,
Redis client) and lazily constructs them. FastAPI route dependencies
(``app.api.deps``) resolve collaborators from this container, keeping wiring in
one place and making everything trivially overridable in tests.

Lifecycle
---------
* :meth:`startup` — called from the FastAPI lifespan handler; validates config,
  configures logging, and opens shared resources.
* :meth:`shutdown` — disposes the DB engine and closes the Redis pool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config.settings import Settings, get_settings
from app.core.logging import configure_logging, get_logger

if TYPE_CHECKING:  # avoid importing heavy/optional deps at module import time
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

logger = get_logger(__name__)


class Container:
    """Owns and lazily builds shared, process-wide resources."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._redis: Redis | None = None

    # --- accessors ---------------------------------------------------------

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            from sqlalchemy.ext.asyncio import create_async_engine

            self._engine = create_async_engine(
                self._settings.db.dsn,
                echo=self._settings.db.echo,
                pool_size=self._settings.db.pool_size,
                max_overflow=self._settings.db.max_overflow,
                pool_pre_ping=self._settings.db.pool_pre_ping,
            )
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._session_factory

    @property
    def redis(self) -> Redis:
        if self._redis is None:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(
                self._settings.redis.dsn,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    # --- lifecycle ---------------------------------------------------------

    async def startup(self) -> None:
        configure_logging()
        self._settings.validate_runtime()
        # Touch resources so misconfiguration surfaces immediately.
        _ = self.engine
        _ = self.redis
        logger.info(
            "container.startup",
            environment=self._settings.app.environment.value,
            default_llm=self._settings.llm.default_provider.value,
            vector_store=self._settings.rag.vector_store.value,
        )

    async def shutdown(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
        logger.info("container.shutdown")


# Process-wide singleton. Tests may replace this with a container built from an
# overridden Settings instance.
container = Container()

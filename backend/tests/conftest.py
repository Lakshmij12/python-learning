"""Shared pytest fixtures.

Provides an in-memory async SQLite engine and a transactional session per test,
so database tests run fast and isolated without a live PostgreSQL instance.
Vector-similarity tests are the only ones that require PostgreSQL and are marked
``integration``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from app.models import Base
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session backed by a fresh in-memory SQLite database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()

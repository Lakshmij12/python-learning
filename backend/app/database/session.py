"""Async database session management.

Exposes the ``get_db`` FastAPI dependency, which yields a request-scoped
``AsyncSession`` from the DI container's session factory and implements the
Unit-of-Work pattern: the session is committed on success and rolled back on any
exception, then always closed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import container


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a transactional scope around a series of operations.

    Commits on clean exit, rolls back on exception, always closes.
    """
    session = container.session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session."""
    async with session_scope() as session:
        yield session

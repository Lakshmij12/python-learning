"""Generic async repository base class.

Encapsulates common CRUD so services depend on a narrow, testable interface
rather than raw SQLAlchemy. Soft-deletable models are filtered to exclude
``deleted_at``-set rows by default, and deletion is soft when supported.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base, SoftDeleteMixin

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """CRUD operations for a single model type."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- helpers -----------------------------------------------------------

    @property
    def _supports_soft_delete(self) -> bool:
        return issubclass(self.model, SoftDeleteMixin)

    def _active_filter(self, stmt: Any, include_deleted: bool) -> Any:
        if self._supports_soft_delete and not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return stmt

    # --- create ------------------------------------------------------------

    async def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def create(self, **kwargs: Any) -> ModelT:
        return await self.add(self.model(**kwargs))

    # --- read --------------------------------------------------------------

    async def get(self, id_: uuid.UUID, *, include_deleted: bool = False) -> ModelT | None:
        stmt = select(self.model).where(self.model.id == id_)  # type: ignore[attr-defined]
        stmt = self._active_filter(stmt, include_deleted)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
        order_desc: bool = True,
        **filters: Any,
    ) -> list[ModelT]:
        stmt = select(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        stmt = self._active_filter(stmt, include_deleted)
        order_col = getattr(self.model, "created_at", None)
        if order_col is not None:
            stmt = stmt.order_by(order_col.desc() if order_desc else order_col.asc())
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, *, include_deleted: bool = False, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        stmt = self._active_filter(stmt, include_deleted)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    # --- update ------------------------------------------------------------

    async def update(self, obj: ModelT, **changes: Any) -> ModelT:
        for key, value in changes.items():
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    # --- delete ------------------------------------------------------------

    async def delete(self, obj: ModelT, *, hard: bool = False) -> None:
        """Soft-delete when supported (unless ``hard``); otherwise remove."""
        if self._supports_soft_delete and not hard:
            obj.deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
            await self.session.flush()
        else:
            await self.session.delete(obj)
            await self.session.flush()

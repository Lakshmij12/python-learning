"""Declarative base and shared model mixins.

All ORM models inherit from :class:`Base`. Reusable columns are provided as
mixins so every table gets consistent primary keys, timestamps, and soft-delete
semantics without duplication.

Cross-dialect notes
-------------------
* ``Uuid`` maps to native ``UUID`` on PostgreSQL and ``CHAR(32)`` elsewhere, so
  the same models run under SQLite in tests.
* ``JSONVariant`` is ``JSONB`` on PostgreSQL and generic ``JSON`` elsewhere.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB on Postgres, JSON on SQLite/others.
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    """Root declarative base shared by every model."""

    type_annotation_map = {dict: JSONVariant}


class UUIDMixin:
    """Adds a UUID primary key generated application-side."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, sort_order=-100
    )


class TimestampMixin:
    """Adds created/updated timestamps maintained by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=100
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        sort_order=101,
    )


class SoftDeleteMixin:
    """Adds a nullable ``deleted_at`` for soft deletion / GDPR-style erasure."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, sort_order=102
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

"""Long-term memory and vector embedding models.

The ``Embedding.vector`` column uses pgvector's ``Vector`` type on PostgreSQL
and falls back to generic ``JSON`` on other dialects (so the model set is fully
creatable under SQLite in tests). Similarity search only runs on PostgreSQL.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.settings import get_settings
from app.database.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import MemoryType

if TYPE_CHECKING:
    from app.models.document import Document

# Embedding dimensionality is driven by configuration (must match the model).
EMBEDDING_DIM = get_settings().llm.embedding_dimensions

# pgvector on Postgres; JSON list elsewhere (tests).
VectorColumn = Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite")


class Memory(UUIDMixin, TimestampMixin, Base):
    """A durable memory item (episodic summary, semantic fact, or profile note)."""

    __tablename__ = "memory"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    memory_type: Mapped[MemoryType] = mapped_column(SAEnum(MemoryType), nullable=False)
    # Encrypted content at rest.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Relevance/decay score for ranking recall.
    importance: Mapped[float] = mapped_column(default=0.5, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta: Mapped[dict] = mapped_column(default=dict)

    embedding: Mapped[Embedding | None] = relationship(
        back_populates="memory", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (Index("ix_memory_user_type", "user_id", "memory_type"),)


class Embedding(UUIDMixin, TimestampMixin, Base):
    """A vector embedding for a memory item or a document chunk.

    Exactly one of ``memory_id`` / ``document_id`` is set (polymorphic source)."""

    __tablename__ = "embeddings"

    memory_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memory.id", ondelete="CASCADE"), index=True, nullable=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # The text that was embedded (chunk / summary).
    chunk: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(default=0, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    vector: Mapped[list[float]] = mapped_column(VectorColumn, nullable=False)
    meta: Mapped[dict] = mapped_column(default=dict)

    memory: Mapped[Memory | None] = relationship(back_populates="embedding")
    document: Mapped[Document | None] = relationship(back_populates="embeddings")

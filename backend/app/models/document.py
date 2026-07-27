"""File and document models (uploads, PDFs, OCR, RAG sources)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import DocumentStatus

if TYPE_CHECKING:
    from app.models.memory import Embedding


class File(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A stored binary asset (image, audio, pdf) referenced by messages/documents."""

    __tablename__ = "files"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(400), nullable=False)
    content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # Object-storage key or filesystem path (never a public URL).
    storage_key: Mapped[str] = mapped_column(String(600), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    meta: Mapped[dict] = mapped_column(default=dict)

    documents: Mapped[list[Document]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )


class Document(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A parsed, chunk-and-embed-able document derived from a file or raw text."""

    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), default="upload", nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False
    )
    # Extracted plaintext (encrypted at rest).
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(default=dict)

    file: Mapped[File | None] = relationship(back_populates="documents")
    embeddings: Mapped[list[Embedding]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

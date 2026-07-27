"""Conversation and message models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import (
    MessageDirection,
    MessageRole,
    MessageStatus,
    MessageType,
)

if TYPE_CHECKING:
    from app.models.user import User


class Conversation(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A thread of messages with a WhatsApp contact (usually just the owner)."""

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # WhatsApp contact identifier (wa_id / E.164).
    contact_wa_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meta: Mapped[dict] = mapped_column(default=dict)

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    __table_args__ = (
        Index("ix_conversations_user_contact", "user_id", "contact_wa_id"),
    )


class Message(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A single message. The ``content`` column holds the ciphertext of the
    message body (encrypted at the application layer); ``content`` is never
    plaintext at rest in production."""

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Provider message id (idempotency / dedupe key from the webhook).
    provider_message_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole), nullable=False)
    direction: Mapped[MessageDirection] = mapped_column(
        SAEnum(MessageDirection), nullable=False
    )
    message_type: Mapped[MessageType] = mapped_column(
        SAEnum(MessageType), default=MessageType.TEXT, nullable=False
    )
    status: Mapped[MessageStatus] = mapped_column(
        SAEnum(MessageStatus), default=MessageStatus.RECEIVED, nullable=False
    )
    # Encrypted body (AES-256-GCM). Plaintext only lives in memory during processing.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Token accounting for cost tracking.
    tokens: Mapped[int | None] = mapped_column(nullable=True)
    meta: Mapped[dict] = mapped_column(default=dict)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

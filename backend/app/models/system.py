"""System models: settings, prompt templates, LLM usage, logs, audit logs."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import AuditAction


class Setting(UUIDMixin, TimestampMixin, Base):
    """A key/value application or per-user setting (model choice, toggles)."""

    __tablename__ = "settings"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[dict] = mapped_column(default=dict)

    __table_args__ = (Index("uq_settings_user_key", "user_id", "key", unique=True),)


class Prompt(UUIDMixin, TimestampMixin, Base):
    """A versioned prompt template managed from the dashboard Prompt Manager."""

    __tablename__ = "prompts"

    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (Index("uq_prompts_name_version", "name", "version", unique=True),)


class LLMUsage(UUIDMixin, TimestampMixin, Base):
    """Per-call LLM usage and cost accounting (dashboard API-usage view)."""

    __tablename__ = "llm_usage"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    provider: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), default="chat", nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Log(UUIDMixin, TimestampMixin, Base):
    """Structured application log persisted for the dashboard Logs view."""

    __tablename__ = "logs"

    level: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    event: Mapped[str] = mapped_column(String(200), nullable=False)
    logger: Mapped[str | None] = mapped_column(String(200), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    context: Mapped[dict] = mapped_column(default=dict)


class AuditLog(UUIDMixin, TimestampMixin, Base):
    """Tamper-evident audit trail of security-relevant actions."""

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[AuditAction] = mapped_column(SAEnum(AuditAction), index=True, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    context: Mapped[dict] = mapped_column(default=dict)

    __table_args__ = (Index("ix_audit_user_action", "user_id", "action"),)

"""Productivity models: tasks, notes, reminders."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.models.enums import Priority, ReminderStatus, TaskStatus


class Task(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A to-do item managed via the assistant (/task)."""

    __tablename__ = "tasks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus), default=TaskStatus.TODO, nullable=False, index=True
    )
    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority), default=Priority.MEDIUM, nullable=False
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict] = mapped_column(default=dict)

    __table_args__ = (Index("ix_tasks_user_status", "user_id", "status"),)


class Note(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A free-form note (/note). Body encrypted at rest."""

    __tablename__ = "notes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[dict] = mapped_column(default=dict)


class Reminder(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A time-based reminder (/remind), dispatched by Celery Beat."""

    __tablename__ = "reminders"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[ReminderStatus] = mapped_column(
        SAEnum(ReminderStatus), default=ReminderStatus.SCHEDULED, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Optional recurrence rule (RFC 5545 RRULE); null = one-shot.
    recurrence: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (Index("ix_reminders_due", "status", "remind_at"),)

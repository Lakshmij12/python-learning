"""DTOs for tasks, notes, and reminders."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Priority, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    priority: Priority = Priority.MEDIUM
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_at: datetime | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: Priority
    due_at: datetime | None
    created_at: datetime


class NoteCreate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1, max_length=50000)


class NoteResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    content: str
    created_at: datetime

"""ORM models package.

Importing this package registers every model on ``Base.metadata`` so Alembic
autogenerate and ``create_all`` see the full schema.
"""

from __future__ import annotations

from app.database.base import Base
from app.models.conversation import Conversation, Message
from app.models.document import Document, File
from app.models.enums import (
    AuditAction,
    DocumentStatus,
    MemoryType,
    MessageDirection,
    MessageRole,
    MessageStatus,
    MessageType,
    Priority,
    ReminderStatus,
    TaskStatus,
)
from app.models.memory import Embedding, Memory
from app.models.productivity import Note, Reminder, Task
from app.models.system import AuditLog, LLMUsage, Log, Prompt, Setting
from app.models.user import ApiKey, Session, User

__all__ = [
    "Base",
    # user / auth
    "User",
    "Session",
    "ApiKey",
    # conversation
    "Conversation",
    "Message",
    # memory
    "Memory",
    "Embedding",
    # documents
    "File",
    "Document",
    # productivity
    "Task",
    "Note",
    "Reminder",
    # system
    "Setting",
    "Prompt",
    "LLMUsage",
    "Log",
    "AuditLog",
    # enums
    "MessageRole",
    "MessageDirection",
    "MessageType",
    "MessageStatus",
    "MemoryType",
    "TaskStatus",
    "Priority",
    "ReminderStatus",
    "DocumentStatus",
    "AuditAction",
]

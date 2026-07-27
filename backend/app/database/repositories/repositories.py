"""Concrete repositories with model-specific queries."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select

from app.database.repositories.base import BaseRepository
from app.models.conversation import Conversation, Message
from app.models.document import Document, File
from app.models.enums import ReminderStatus
from app.models.memory import Embedding, Memory
from app.models.productivity import Note, Reminder, Task
from app.models.system import AuditLog, LLMUsage, Log, Prompt, Setting
from app.models.user import ApiKey, Session, User


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(
            User.email == email.lower(), User.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SessionRepository(BaseRepository[Session]):
    model = Session

    async def get_by_refresh_hash(self, token_hash: str) -> Session | None:
        stmt = select(Session).where(
            Session.refresh_token_hash == token_hash, Session.revoked_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class ApiKeyRepository(BaseRepository[ApiKey]):
    model = ApiKey

    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        stmt = select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.revoked_at.is_(None),
            ApiKey.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def get_or_create(self, user_id: uuid.UUID, contact_wa_id: str) -> Conversation:
        stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.contact_wa_id == contact_wa_id,
            Conversation.deleted_at.is_(None),
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing
        return await self.create(user_id=user_id, contact_wa_id=contact_wa_id)


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def get_by_provider_id(self, provider_message_id: str) -> Message | None:
        stmt = select(Message).where(Message.provider_message_id == provider_message_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def recent_for_conversation(
        self, conversation_id: uuid.UUID, limit: int = 12
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.deleted_at.is_(None),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        rows.reverse()  # chronological
        return rows


class MemoryRepository(BaseRepository[Memory]):
    model = Memory


class EmbeddingRepository(BaseRepository[Embedding]):
    model = Embedding

    async def similar(
        self, query_vector: list[float], *, top_k: int = 6
    ) -> list[Embedding]:
        """Nearest-neighbour search (PostgreSQL/pgvector only).

        Uses cosine distance via the ``<=>`` operator exposed by pgvector's
        SQLAlchemy type. On non-Postgres dialects this raises at query time.
        """
        stmt = (
            select(Embedding)
            .order_by(Embedding.vector.cosine_distance(query_vector))
            .limit(top_k)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class DocumentRepository(BaseRepository[Document]):
    model = Document


class FileRepository(BaseRepository[File]):
    model = File


class TaskRepository(BaseRepository[Task]):
    model = Task


class NoteRepository(BaseRepository[Note]):
    model = Note


class ReminderRepository(BaseRepository[Reminder]):
    model = Reminder

    async def due(self, before: datetime) -> list[Reminder]:
        """Scheduled reminders whose time has arrived (for Celery Beat)."""
        stmt = (
            select(Reminder)
            .where(
                Reminder.status == ReminderStatus.SCHEDULED,
                Reminder.remind_at <= before,
                Reminder.deleted_at.is_(None),
            )
            .order_by(Reminder.remind_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


class SettingRepository(BaseRepository[Setting]):
    model = Setting


class PromptRepository(BaseRepository[Prompt]):
    model = Prompt


class LLMUsageRepository(BaseRepository[LLMUsage]):
    model = LLMUsage


class LogRepository(BaseRepository[Log]):
    model = Log


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

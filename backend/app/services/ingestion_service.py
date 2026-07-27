"""Inbound message ingestion.

Persists a normalised inbound WhatsApp message: authorises the sender (privacy:
only the account owner's number is accepted), resolves the conversation,
deduplicates by provider message id, and stores the body **encrypted at rest**.

Returns the persisted ``Message`` (or ``None`` if it was a duplicate) so the
caller (webhook flow) can enqueue agent processing.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.repositories.repositories import (
    ConversationRepository,
    MessageRepository,
    UserRepository,
)
from app.messaging.base import InboundMessage
from app.models.conversation import Message
from app.models.enums import MessageDirection, MessageRole, MessageStatus
from app.security.crypto import encrypt

logger = get_logger(__name__)


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.conversations = ConversationRepository(session)
        self.messages = MessageRepository(session)

    async def ingest(self, inbound: InboundMessage) -> Message | None:
        """Persist an inbound message. Returns None if unauthorised/duplicate."""
        # Idempotency: skip if we've already stored this provider id.
        if inbound.provider_message_id:
            existing = await self.messages.get_by_provider_id(inbound.provider_message_id)
            if existing is not None:
                logger.info("ingest.duplicate", provider_id=inbound.provider_message_id)
                return None

        user = await self._authorise_owner(inbound.from_number)
        if user is None:
            # Privacy guarantee: never process messages from other numbers.
            logger.warning("ingest.unauthorised_sender")
            return None

        conversation = await self.conversations.get_or_create(user.id, inbound.from_number)

        message = await self.messages.create(
            conversation_id=conversation.id,
            provider_message_id=inbound.provider_message_id or None,
            role=MessageRole.USER,
            direction=MessageDirection.INBOUND,
            message_type=inbound.message_type,
            status=MessageStatus.RECEIVED,
            content=encrypt(inbound.text) if inbound.text else None,
            meta={
                "media_id": inbound.media_id,
                "mime_type": inbound.media_mime_type,
            },
        )
        await self.conversations.update(conversation, last_message_at=message.created_at)
        return message

    async def _authorise_owner(self, from_number: str):  # noqa: ANN202
        """Return the owner user iff ``from_number`` matches the configured owner.

        Falls back to the single active user when no owner number is configured
        (first-run/local convenience).
        """
        from app.config.settings import get_settings

        owner_number = get_settings().whatsapp.owner_phone_number
        normalised = from_number.lstrip("+")
        if owner_number and normalised != owner_number.lstrip("+"):
            return None
        # Single-tenant: the assistant serves one active account owner.
        return await self.users.first_active()

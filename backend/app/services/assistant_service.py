"""Assistant service: turn a stored inbound message into a sent reply.

Called after ingestion (from the webhook flow / Celery). It loads the inbound
message, routes it to a command handler or the agent, persists the assistant's
reply (encrypted), and sends it back over the messaging provider.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.handlers import CommandRouter
from app.core.logging import get_logger
from app.database.repositories.repositories import (
    ConversationRepository,
    MessageRepository,
)
from app.llm.router import LLMRouter
from app.messaging.base import MessagingProvider
from app.models.enums import MessageDirection, MessageRole, MessageStatus, MessageType
from app.security.crypto import decrypt, encrypt

logger = get_logger(__name__)


class AssistantService:
    def __init__(
        self,
        session: AsyncSession,
        router: LLMRouter,
        provider: MessagingProvider,
        *,
        redis: object | None = None,
    ) -> None:
        self.session = session
        self.router = router
        self.provider = provider
        self.redis = redis
        self.messages = MessageRepository(session)
        self.conversations = ConversationRepository(session)

    async def respond_to(self, message_id: uuid.UUID) -> str | None:
        """Generate and send a reply for a stored inbound message."""
        inbound = await self.messages.get(message_id)
        if inbound is None:
            return None
        conversation = await self.conversations.get(inbound.conversation_id)
        if conversation is None:
            return None

        text = decrypt(inbound.content) if inbound.content else ""
        if not text:
            return None  # media-only handling lives in the worker phase

        await self.messages.update(inbound, status=MessageStatus.PROCESSING)

        # Command shortcut, else the agent.
        if CommandRouter.is_command(text):
            reply = await CommandRouter.handle(
                text, session=self.session, user_id=conversation.user_id
            )
        else:
            # Imported lazily to avoid a heavy import at module load.
            from app.agents.orchestrator import AgentService

            agent = AgentService(self.session, self.router, redis=self.redis)
            reply = await agent.handle(
                user_id=conversation.user_id,
                conversation_id=conversation.id,
                text=text,
            )

        await self._persist_and_send(conversation.contact_wa_id, conversation.id, reply)
        await self.messages.update(inbound, status=MessageStatus.READ)
        return reply

    async def _persist_and_send(
        self, to_number: str, conversation_id: uuid.UUID, reply: str
    ) -> None:
        stored = await self.messages.create(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.TEXT,
            status=MessageStatus.QUEUED,
            content=encrypt(reply),
        )
        try:
            result = await self.provider.send_text(to=to_number, text=reply)
            await self.messages.update(
                stored,
                status=MessageStatus.SENT,
                provider_message_id=result.provider_message_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("assistant.send_failed", error=str(exc))
            await self.messages.update(stored, status=MessageStatus.FAILED)

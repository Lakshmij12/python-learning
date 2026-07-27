"""WhatsApp webhook orchestration.

Validates the payload signature, applies replay protection, and ingests each
inbound message. Returns the ids of newly-stored messages so the router can
enqueue agent processing (wired in the agent phase).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.messaging.base import MessagingProvider
from app.messaging.replay import ReplayGuard
from app.services.ingestion_service import IngestionService

logger = get_logger(__name__)


class WebhookService:
    def __init__(
        self,
        session: AsyncSession,
        provider: MessagingProvider,
        replay_guard: ReplayGuard,
    ) -> None:
        self.session = session
        self.provider = provider
        self.replay = replay_guard
        self.ingestion = IngestionService(session)

    async def handle_event(
        self, *, raw_body: bytes, signature_header: str | None
    ) -> list[uuid.UUID]:
        """Verify + ingest a webhook event. Returns new message ids."""
        # 1. Authenticate the payload (HMAC) — raises on mismatch.
        self.provider.verify_signature(payload=raw_body, signature_header=signature_header)

        import json

        payload = json.loads(raw_body.decode("utf-8"))
        inbound_messages = self.provider.parse_inbound(payload)

        stored: list[uuid.UUID] = []
        for inbound in inbound_messages:
            # 2. Freshness + idempotency.
            self.replay.check_fresh(inbound.timestamp)
            if await self.replay.is_duplicate(inbound.provider_message_id):
                logger.info("webhook.duplicate_skipped", pid=inbound.provider_message_id)
                continue
            # 3. Persist (owner-authorised, encrypted).
            message = await self.ingestion.ingest(inbound)
            if message is not None:
                stored.append(message.id)

        return stored

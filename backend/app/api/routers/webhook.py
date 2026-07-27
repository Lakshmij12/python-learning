"""WhatsApp Cloud API webhook router.

* ``GET  /webhook/whatsapp`` — subscription handshake (echoes hub.challenge).
* ``POST /webhook/whatsapp`` — receives events; verifies signature + replay,
  ingests messages, and returns 200 quickly (heavy work is offloaded).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import container
from app.core.logging import get_logger
from app.database.session import get_db
from app.messaging.base import MessagingProvider
from app.messaging.factory import get_messaging_provider
from app.messaging.replay import ReplayGuard
from app.services.webhook_service import WebhookService

logger = get_logger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


def get_provider() -> MessagingProvider:
    return get_messaging_provider()


@router.get("/whatsapp", response_class=PlainTextResponse)
async def verify(
    provider: Annotated[MessagingProvider, Depends(get_provider)],
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> str:
    """Meta subscription handshake. Returns the challenge on success."""
    return provider.verify_webhook(
        mode=hub_mode, token=hub_verify_token, challenge=hub_challenge
    )


@router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def receive(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    provider: Annotated[MessagingProvider, Depends(get_provider)],
    x_hub_signature_256: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> Response:
    """Receive and ingest a webhook event."""
    raw_body = await request.body()
    replay = ReplayGuard(_safe_redis())
    service = WebhookService(db, provider, replay)
    message_ids = await service.handle_event(
        raw_body=raw_body, signature_header=x_hub_signature_256
    )
    if message_ids:
        # Agent processing is enqueued here (wired in the agent phase).
        logger.info("webhook.ingested", count=len(message_ids))
    # Always 200 so Meta does not retry a successfully-received event.
    return Response(status_code=status.HTTP_200_OK)


def _safe_redis() -> object | None:
    """Return the Redis client if available; None otherwise (guard degrades)."""
    try:
        return container.redis
    except Exception:  # noqa: BLE001
        return None

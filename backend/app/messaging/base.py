"""Messaging provider port (interface).

Any messaging channel (WhatsApp Cloud API today; Twilio/360dialog later) is
implemented as a ``MessagingProvider``. Services depend only on this interface,
so the channel is swappable without touching business logic.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.models.enums import MessageType


@dataclass(slots=True)
class InboundMessage:
    """A normalised inbound message, provider-agnostic."""

    provider_message_id: str
    from_number: str
    timestamp: int
    message_type: MessageType
    text: str | None = None
    # For media messages: the provider media id to download later.
    media_id: str | None = None
    media_mime_type: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass(slots=True)
class OutboundResult:
    provider_message_id: str | None
    raw: dict = field(default_factory=dict)


class MessagingProvider(ABC):
    """Abstract messaging channel."""

    name: str = "base"

    @abstractmethod
    def verify_webhook(self, *, mode: str | None, token: str | None, challenge: str | None) -> str:
        """Handle the provider's subscription handshake (GET).

        Returns the challenge to echo back on success; raises on failure.
        """

    @abstractmethod
    def verify_signature(self, *, payload: bytes, signature_header: str | None) -> None:
        """Validate the webhook payload signature; raise on mismatch."""

    @abstractmethod
    def parse_inbound(self, payload: dict) -> list[InboundMessage]:
        """Extract normalised inbound messages from a webhook payload."""

    @abstractmethod
    async def send_text(self, *, to: str, text: str) -> OutboundResult:
        """Send a plain-text message."""

    @abstractmethod
    async def mark_read(self, *, provider_message_id: str) -> None:
        """Mark an inbound message as read (best-effort)."""

    @abstractmethod
    async def download_media(self, *, media_id: str) -> tuple[bytes, str]:
        """Download media bytes; returns ``(content, mime_type)``."""

    def new_request_id(self) -> str:
        return uuid.uuid4().hex

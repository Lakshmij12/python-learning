"""WhatsApp Cloud API (Meta Business Platform) messaging provider.

Implements the official, ToS-compliant integration:
* GET webhook subscription handshake (``hub.*`` params),
* ``X-Hub-Signature-256`` HMAC validation on every event,
* inbound message normalisation,
* outbound text send, read receipts, and media download via the Graph API.
"""

from __future__ import annotations

import hashlib
import hmac

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config.settings import get_settings
from app.core.exceptions import MessagingProviderError, WebhookVerificationError
from app.core.logging import get_logger
from app.messaging.base import InboundMessage, MessagingProvider, OutboundResult
from app.models.enums import MessageType

logger = get_logger(__name__)

# Map Cloud API message types to our internal enum.
_TYPE_MAP = {
    "text": MessageType.TEXT,
    "image": MessageType.IMAGE,
    "audio": MessageType.AUDIO,
    "voice": MessageType.AUDIO,
    "video": MessageType.VIDEO,
    "document": MessageType.DOCUMENT,
    "location": MessageType.LOCATION,
}


class CloudApiProvider(MessagingProvider):
    name = "whatsapp_cloud_api"

    def __init__(self) -> None:
        self._settings = get_settings().whatsapp

    # --- webhook verification ---------------------------------------------

    def verify_webhook(
        self, *, mode: str | None, token: str | None, challenge: str | None
    ) -> str:
        expected = self._settings.verify_token.get_secret_value()
        if mode == "subscribe" and token and hmac.compare_digest(token, expected):
            return challenge or ""
        raise WebhookVerificationError("Webhook verify token mismatch.")

    def verify_signature(self, *, payload: bytes, signature_header: str | None) -> None:
        secret = self._settings.app_secret.get_secret_value()
        if not secret:
            raise WebhookVerificationError("App secret not configured.")
        if not signature_header or not signature_header.startswith("sha256="):
            raise WebhookVerificationError("Missing or malformed signature header.")
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        provided = signature_header.removeprefix("sha256=")
        if not hmac.compare_digest(expected, provided):
            raise WebhookVerificationError("Webhook signature mismatch.")

    # --- inbound parsing ---------------------------------------------------

    def parse_inbound(self, payload: dict) -> list[InboundMessage]:
        messages: list[InboundMessage] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    messages.append(self._parse_message(msg))
        return messages

    def _parse_message(self, msg: dict) -> InboundMessage:
        raw_type = msg.get("type", "text")
        mtype = _TYPE_MAP.get(raw_type, MessageType.TEXT)
        text: str | None = None
        media_id: str | None = None
        mime: str | None = None

        if raw_type == "text":
            text = msg.get("text", {}).get("body")
        elif raw_type in {"image", "audio", "voice", "video", "document"}:
            media = msg.get(raw_type, {})
            media_id = media.get("id")
            mime = media.get("mime_type")
            text = media.get("caption")

        return InboundMessage(
            provider_message_id=msg.get("id", ""),
            from_number=msg.get("from", ""),
            timestamp=int(msg.get("timestamp", 0)),
            message_type=mtype,
            text=text,
            media_id=media_id,
            media_mime_type=mime,
            raw=msg,
        )

    # --- outbound ----------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=8), reraise=True)
    async def send_text(self, *, to: str, text: str) -> OutboundResult:
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        data = await self._post(f"/{self._settings.phone_number_id}/messages", body)
        msg_id = None
        if isinstance(data.get("messages"), list) and data["messages"]:
            msg_id = data["messages"][0].get("id")
        return OutboundResult(provider_message_id=msg_id, raw=data)

    async def mark_read(self, *, provider_message_id: str) -> None:
        body = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": provider_message_id,
        }
        try:
            await self._post(f"/{self._settings.phone_number_id}/messages", body)
        except MessagingProviderError:
            logger.warning("mark_read.failed", message_id=provider_message_id)

    async def download_media(self, *, media_id: str) -> tuple[bytes, str]:
        # Two-step: resolve the media URL, then download it (auth required).
        async with self._client() as client:
            meta = await client.get(f"{self._settings.graph_base_url}/{media_id}")
            meta.raise_for_status()
            info = meta.json()
            url = info["url"]
            mime = info.get("mime_type", "application/octet-stream")
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content, mime

    # --- http helpers ------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        token = self._settings.access_token.get_secret_value()
        return httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    async def _post(self, path: str, json: dict) -> dict:
        url = f"{self._settings.graph_base_url}{path}"
        async with self._client() as client:
            try:
                resp = await client.post(url, json=json)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error("cloud_api.http_error", status=exc.response.status_code, path=path)
                raise MessagingProviderError(
                    "WhatsApp Cloud API request failed.",
                    detail={"status": exc.response.status_code},
                ) from exc
            except httpx.HTTPError as exc:
                raise MessagingProviderError("WhatsApp Cloud API unreachable.") from exc
            return resp.json()

"""Unit tests for the WhatsApp Cloud API provider."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from app.config.settings import get_settings
from app.core.exceptions import WebhookVerificationError
from app.models.enums import MessageType


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me-123")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1234567890")
    get_settings.cache_clear()
    from app.messaging.providers.cloud_api import CloudApiProvider

    yield CloudApiProvider()
    get_settings.cache_clear()


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# --- webhook verification ---------------------------------------------------


def test_verify_webhook_success(provider) -> None:  # noqa: ANN001
    assert (
        provider.verify_webhook(mode="subscribe", token="verify-me-123", challenge="CHALLENGE")
        == "CHALLENGE"
    )


def test_verify_webhook_wrong_token(provider) -> None:  # noqa: ANN001
    with pytest.raises(WebhookVerificationError):
        provider.verify_webhook(mode="subscribe", token="wrong", challenge="X")


def test_verify_signature_valid(provider) -> None:  # noqa: ANN001
    body = b'{"hello":"world"}'
    provider.verify_signature(payload=body, signature_header=_sign("test-app-secret", body))


def test_verify_signature_invalid(provider) -> None:  # noqa: ANN001
    body = b'{"hello":"world"}'
    with pytest.raises(WebhookVerificationError):
        provider.verify_signature(payload=body, signature_header="sha256=deadbeef")


def test_verify_signature_missing_header(provider) -> None:  # noqa: ANN001
    with pytest.raises(WebhookVerificationError):
        provider.verify_signature(payload=b"{}", signature_header=None)


def test_verify_signature_tampered_body(provider) -> None:  # noqa: ANN001
    sig = _sign("test-app-secret", b'{"a":1}')
    with pytest.raises(WebhookVerificationError):
        provider.verify_signature(payload=b'{"a":2}', signature_header=sig)


# --- inbound parsing --------------------------------------------------------


def test_parse_inbound_text(provider) -> None:  # noqa: ANN001
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.123",
                                    "from": "15551234567",
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": "Hello assistant"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    msgs = provider.parse_inbound(payload)
    assert len(msgs) == 1
    m = msgs[0]
    assert m.provider_message_id == "wamid.123"
    assert m.from_number == "15551234567"
    assert m.message_type == MessageType.TEXT
    assert m.text == "Hello assistant"


def test_parse_inbound_media(provider) -> None:  # noqa: ANN001
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.img",
                                    "from": "15551234567",
                                    "timestamp": "1700000001",
                                    "type": "image",
                                    "image": {
                                        "id": "media-987",
                                        "mime_type": "image/jpeg",
                                        "caption": "a photo",
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    m = provider.parse_inbound(payload)[0]
    assert m.message_type == MessageType.IMAGE
    assert m.media_id == "media-987"
    assert m.media_mime_type == "image/jpeg"
    assert m.text == "a photo"


def test_parse_inbound_ignores_status_events(provider) -> None:  # noqa: ANN001
    payload = {"entry": [{"changes": [{"value": {"statuses": [{"status": "read"}]}}]}]}
    assert provider.parse_inbound(payload) == []
    # sanity: json round-trips
    assert json.loads(json.dumps(payload)) == payload

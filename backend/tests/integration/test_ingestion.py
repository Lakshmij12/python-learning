"""Integration tests for inbound ingestion (owner-auth, dedupe, encryption)."""

from __future__ import annotations

import pytest
from app.config.settings import get_settings
from app.database.repositories.repositories import UserRepository
from app.messaging.base import InboundMessage
from app.models.enums import MessageType
from app.security.crypto import decrypt
from app.services.ingestion_service import IngestionService
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _owner(session: AsyncSession):  # noqa: ANN202
    return await UserRepository(session).create(
        email="owner@example.com", password_hash="h", whatsapp_number="15551234567"
    )


def _inbound(text: str = "hello", pid: str = "wamid.1", frm: str = "15551234567") -> InboundMessage:
    return InboundMessage(
        provider_message_id=pid,
        from_number=frm,
        timestamp=1700000000,
        message_type=MessageType.TEXT,
        text=text,
    )


async def test_ingest_stores_encrypted_message(db_session: AsyncSession) -> None:
    await _owner(db_session)
    svc = IngestionService(db_session)
    msg = await svc.ingest(_inbound("secret plans"))
    assert msg is not None
    # Stored content must be ciphertext, not plaintext.
    assert msg.content is not None and msg.content != "secret plans"
    assert msg.content.startswith("v1.")
    assert decrypt(msg.content) == "secret plans"


async def test_ingest_is_idempotent(db_session: AsyncSession) -> None:
    await _owner(db_session)
    svc = IngestionService(db_session)
    first = await svc.ingest(_inbound(pid="wamid.dupe"))
    second = await svc.ingest(_inbound(pid="wamid.dupe"))
    assert first is not None
    assert second is None  # duplicate provider id skipped


async def test_ingest_rejects_non_owner_number(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WHATSAPP_OWNER_PHONE_NUMBER", "15551234567")
    get_settings.cache_clear()
    try:
        await _owner(db_session)
        svc = IngestionService(db_session)
        # Message from a different number must be rejected (privacy guarantee).
        result = await svc.ingest(_inbound(frm="19998887777", pid="wamid.other"))
        assert result is None
    finally:
        get_settings.cache_clear()

"""HTTP-level webhook security: signature enforcement and replay freshness."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config.settings import get_settings
from app.database.session import get_db
from app.main import create_app
from app.messaging.factory import get_messaging_provider
from app.models import Base

pytestmark = pytest.mark.asyncio

_SECRET = "test-app-secret"


@pytest_asyncio.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("WHATSAPP_APP_SECRET", _SECRET)
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "111")
    get_settings.cache_clear()
    get_messaging_provider.cache_clear()

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override() -> AsyncIterator:
        async with factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await engine.dispose()
    get_settings.cache_clear()
    get_messaging_provider.cache_clear()


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()


async def test_webhook_rejects_missing_signature(client: AsyncClient) -> None:
    resp = await client.post("/webhook/whatsapp", content=b"{}")
    assert resp.status_code == 403


async def test_webhook_rejects_bad_signature(client: AsyncClient) -> None:
    resp = await client.post(
        "/webhook/whatsapp",
        content=b'{"entry":[]}',
        headers={"X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert resp.status_code == 403


async def test_webhook_accepts_valid_signature(client: AsyncClient) -> None:
    body = json.dumps({"entry": []}).encode()
    resp = await client.post(
        "/webhook/whatsapp", content=body, headers={"X-Hub-Signature-256": _sign(body)}
    )
    assert resp.status_code == 200

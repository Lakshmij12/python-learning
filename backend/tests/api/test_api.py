"""API tests exercising the ASGI app end-to-end (SQLite-backed)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from app.database.session import get_db
from app.main import create_app
from app.models import Base
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # One shared in-memory DB across all connections for the test app.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await engine.dispose()


async def test_health_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_security_headers_present(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "X-Request-ID" in resp.headers


async def test_register_login_and_me(client: AsyncClient) -> None:
    reg = await client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "StrongPass123"},
    )
    assert reg.status_code == 201, reg.text

    login = await client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"


async def test_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_task_crud_flow(client: AsyncClient) -> None:
    await client.post(
        "/auth/register", json={"email": "t@example.com", "password": "StrongPass123"}
    )
    login = await client.post(
        "/auth/login", json={"email": "t@example.com", "password": "StrongPass123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = await client.post("/tasks", json={"title": "Write tests"}, headers=headers)
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    listing = await client.get("/tasks", headers=headers)
    assert listing.status_code == 200
    assert any(t["id"] == task_id for t in listing.json())

    patched = await client.patch(f"/tasks/{task_id}", json={"status": "done"}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["status"] == "done"

    deleted = await client.delete(f"/tasks/{task_id}", headers=headers)
    assert deleted.status_code == 204


async def test_webhook_verify_handshake(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config.settings import get_settings

    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me-123")
    get_settings.cache_clear()
    from app.messaging.factory import get_messaging_provider

    get_messaging_provider.cache_clear()
    try:
        resp = await client.get(
            "/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me-123",
                "hub.challenge": "CHALLENGE_ACCEPTED",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "CHALLENGE_ACCEPTED"
    finally:
        get_settings.cache_clear()
        get_messaging_provider.cache_clear()

"""Integration tests for the authentication service (SQLite-backed)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.security import tokens
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio


async def test_register_then_login(db_session: AsyncSession) -> None:
    svc = AuthService(db_session)
    user = await svc.register(email="owner@example.com", password="StrongPass123")
    assert user.email == "owner@example.com"

    pair = await svc.authenticate(
        email="owner@example.com", password="StrongPass123", user_agent="pytest", ip="127.0.0.1"
    )
    claims = tokens.decode_access_token(pair.access_token)
    assert claims["sub"] == str(user.id)


async def test_duplicate_registration_conflicts(db_session: AsyncSession) -> None:
    svc = AuthService(db_session)
    await svc.register(email="dup@example.com", password="StrongPass123")
    with pytest.raises(ConflictError):
        await svc.register(email="dup@example.com", password="StrongPass123")


async def test_wrong_password_rejected(db_session: AsyncSession) -> None:
    svc = AuthService(db_session)
    await svc.register(email="a@example.com", password="StrongPass123")
    with pytest.raises(AuthenticationError):
        await svc.authenticate(
            email="a@example.com", password="nope", user_agent=None, ip=None
        )


async def test_unknown_user_rejected(db_session: AsyncSession) -> None:
    svc = AuthService(db_session)
    with pytest.raises(AuthenticationError):
        await svc.authenticate(
            email="ghost@example.com", password="whatever12", user_agent=None, ip=None
        )


async def test_refresh_rotates_and_revokes_old(db_session: AsyncSession) -> None:
    svc = AuthService(db_session)
    await svc.register(email="r@example.com", password="StrongPass123")
    pair = await svc.authenticate(
        email="r@example.com", password="StrongPass123", user_agent=None, ip=None
    )
    new_pair = await svc.refresh(refresh_token=pair.refresh_token)
    assert new_pair.refresh_token != pair.refresh_token
    # Old refresh token must no longer work (rotation).
    with pytest.raises(AuthenticationError):
        await svc.refresh(refresh_token=pair.refresh_token)


async def test_logout_revokes_session(db_session: AsyncSession) -> None:
    svc = AuthService(db_session)
    await svc.register(email="l@example.com", password="StrongPass123")
    pair = await svc.authenticate(
        email="l@example.com", password="StrongPass123", user_agent=None, ip=None
    )
    await svc.logout(refresh_token=pair.refresh_token)
    with pytest.raises(AuthenticationError):
        await svc.refresh(refresh_token=pair.refresh_token)

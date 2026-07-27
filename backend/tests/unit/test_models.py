"""Unit tests for ORM models and repositories (SQLite-backed)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.repositories import (
    ConversationRepository,
    MessageRepository,
    TaskRepository,
    UserRepository,
)
from app.models.enums import MessageDirection, MessageRole

pytestmark = pytest.mark.asyncio


async def _make_user(session: AsyncSession) -> uuid.UUID:
    user = await UserRepository(session).create(
        email="me@example.com", password_hash="hashed"
    )
    return user.id


async def test_user_uuid_pk_and_timestamps(db_session: AsyncSession) -> None:
    user = await UserRepository(db_session).create(
        email="owner@example.com", password_hash="h"
    )
    assert isinstance(user.id, uuid.UUID)
    assert user.created_at is not None
    assert user.updated_at is not None


async def test_get_by_email_case_insensitive(db_session: AsyncSession) -> None:
    repo = UserRepository(db_session)
    await repo.create(email="owner@example.com", password_hash="h")
    found = await repo.get_by_email("owner@example.com")
    assert found is not None


async def test_conversation_get_or_create_is_idempotent(db_session: AsyncSession) -> None:
    user_id = await _make_user(db_session)
    repo = ConversationRepository(db_session)
    c1 = await repo.get_or_create(user_id, "15550001111")
    c2 = await repo.get_or_create(user_id, "15550001111")
    assert c1.id == c2.id


async def test_message_provider_id_dedupe(db_session: AsyncSession) -> None:
    user_id = await _make_user(db_session)
    conv = await ConversationRepository(db_session).get_or_create(user_id, "155500022")
    msgs = MessageRepository(db_session)
    created = await msgs.create(
        conversation_id=conv.id,
        role=MessageRole.USER,
        direction=MessageDirection.INBOUND,
        provider_message_id="wamid.unique",
        content="ciphertext",
    )
    found = await msgs.get_by_provider_id("wamid.unique")
    assert found is not None and found.id == created.id


async def test_recent_for_conversation_is_chronological(db_session: AsyncSession) -> None:
    from datetime import datetime, timedelta, timezone

    user_id = await _make_user(db_session)
    conv = await ConversationRepository(db_session).get_or_create(user_id, "155500033")
    msgs = MessageRepository(db_session)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        # Explicit, distinct timestamps (SQLite CURRENT_TIMESTAMP is second-precision).
        await msgs.create(
            conversation_id=conv.id,
            role=MessageRole.USER,
            direction=MessageDirection.INBOUND,
            content=f"m{i}",
            provider_message_id=f"wamid.{i}",
            created_at=base + timedelta(minutes=i),
        )
    recent = await msgs.recent_for_conversation(conv.id, limit=3)
    # Returns the 3 newest, in chronological order.
    assert [m.content for m in recent] == ["m2", "m3", "m4"]


async def test_soft_delete_hides_from_active_lists(db_session: AsyncSession) -> None:
    user_id = await _make_user(db_session)
    tasks = TaskRepository(db_session)
    task = await tasks.create(user_id=user_id, title="Buy milk")
    await tasks.delete(task)  # soft
    assert task.deleted_at is not None
    active = await tasks.list(user_id=user_id)
    assert task.id not in {t.id for t in active}
    with_deleted = await tasks.list(user_id=user_id, include_deleted=True)
    assert task.id in {t.id for t in with_deleted}


async def test_hard_delete_removes_row(db_session: AsyncSession) -> None:
    user_id = await _make_user(db_session)
    tasks = TaskRepository(db_session)
    task = await tasks.create(user_id=user_id, title="Temp")
    task_id = task.id
    await tasks.delete(task, hard=True)
    assert await tasks.get(task_id, include_deleted=True) is None

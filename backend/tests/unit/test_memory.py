"""Tests for working memory and long-term memory service."""

from __future__ import annotations

import uuid

import pytest

from app.llm.base import ChatResult, EmbeddingResult, Role, Usage
from app.memory.service import MemoryService
from app.memory.working import WorkingMemory
from app.models.enums import MemoryType

pytestmark = pytest.mark.asyncio


class FakeRedis:
    """Minimal async Redis list emulation for WorkingMemory tests."""

    def __init__(self) -> None:
        self.store: dict[str, list[str]] = {}

    async def rpush(self, key: str, value: str) -> int:
        self.store.setdefault(key, []).append(value)
        return len(self.store[key])

    async def ltrim(self, key: str, start: int, end: int) -> None:
        items = self.store.get(key, [])
        # Emulate Redis negative-index inclusive trim.
        self.store[key] = items[start:] if end == -1 else items[start : end + 1]

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self.store.get(key, [])
        return items if end == -1 else items[start : end + 1]

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


class FakeRouter:
    async def embed(self, texts, *, user_id=None):  # noqa: ANN001
        return EmbeddingResult(
            vectors=[[0.1, 0.2, 0.3] for _ in texts], provider="fake", model="fake-embed"
        )

    async def chat(self, messages, *, tools=None, temperature=None, max_tokens=None, user_id=None):  # noqa: ANN001
        return ChatResult(content="ok", provider="fake", model="fake", usage=Usage(1, 1))


async def test_working_memory_roundtrip_and_encryption() -> None:
    redis = FakeRedis()
    wm = WorkingMemory(redis)
    cid = uuid.uuid4()
    await wm.append(cid, Role.USER, "hello world")
    # Stored payload must be ciphertext, not the plaintext.
    stored = redis.store[wm._key(cid)][0]
    assert "hello world" not in stored
    msgs = await wm.get(cid)
    assert len(msgs) == 1 and msgs[0].content == "hello world"


async def test_working_memory_trims_to_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config.settings import get_settings

    monkeypatch.setenv("RAG_WORKING_MEMORY_TURNS", "3")
    get_settings.cache_clear()
    try:
        wm = WorkingMemory(FakeRedis())
        cid = uuid.uuid4()
        for i in range(6):
            await wm.append(cid, Role.USER, f"msg{i}")
        msgs = await wm.get(cid)
        assert [m.content for m in msgs] == ["msg3", "msg4", "msg5"]
    finally:
        get_settings.cache_clear()


async def test_working_memory_without_redis_is_noop() -> None:
    wm = WorkingMemory(None)
    cid = uuid.uuid4()
    await wm.append(cid, Role.USER, "x")
    assert await wm.get(cid) == []


async def test_remember_persists_memory_and_embedding(db_session) -> None:  # noqa: ANN001
    from sqlalchemy import func, select

    from app.models.memory import Embedding, Memory

    user_id = uuid.uuid4()
    svc = MemoryService(db_session, FakeRouter())  # type: ignore[arg-type]
    mem = await svc.remember(user_id=user_id, content="Owner prefers metric units",
                             memory_type=MemoryType.PROFILE)
    assert mem.content != "Owner prefers metric units"  # encrypted
    mem_count = (await db_session.execute(select(func.count()).select_from(Memory))).scalar_one()
    emb_count = (await db_session.execute(select(func.count()).select_from(Embedding))).scalar_one()
    assert mem_count == 1 and emb_count == 1


async def test_recall_returns_empty_without_pgvector(db_session) -> None:  # noqa: ANN001
    # SQLite cannot run the vector distance operator; recall must degrade to [].
    svc = MemoryService(db_session, FakeRouter())  # type: ignore[arg-type]
    result = await svc.recall(user_id=uuid.uuid4(), query="units?")
    assert result == []

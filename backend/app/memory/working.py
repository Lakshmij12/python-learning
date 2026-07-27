"""Working (short-term) memory — a bounded window of recent turns in Redis.

Gives the agent fast access to the last N turns of a conversation without a DB
round-trip. Content is stored encrypted (same envelope as at-rest data). The
store degrades gracefully: with no Redis, callers fall back to the database.
"""

from __future__ import annotations

import contextlib
import json
import uuid

from app.config.settings import get_settings
from app.core.logging import get_logger
from app.llm.base import ChatMessage, Role
from app.security.crypto import decrypt, encrypt

logger = get_logger(__name__)


class WorkingMemory:
    """Bounded per-conversation turn window backed by a Redis list."""

    def __init__(self, redis: object | None) -> None:
        self._redis = redis
        self._max_turns = get_settings().rag.working_memory_turns

    def _key(self, conversation_id: uuid.UUID) -> str:
        return f"mem:working:{conversation_id}"

    async def append(self, conversation_id: uuid.UUID, role: Role, content: str) -> None:
        if self._redis is None:
            return
        entry = json.dumps({"role": role.value, "content": encrypt(content)})
        key = self._key(conversation_id)
        try:
            await self._redis.rpush(key, entry)  # type: ignore[attr-defined]
            await self._redis.ltrim(key, -self._max_turns, -1)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            logger.warning("working_memory.redis_unavailable")

    async def get(self, conversation_id: uuid.UUID) -> list[ChatMessage]:
        if self._redis is None:
            return []
        try:
            raw = await self._redis.lrange(self._key(conversation_id), 0, -1)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return []
        messages: list[ChatMessage] = []
        for item in raw:
            data = json.loads(item)
            messages.append(
                ChatMessage(role=Role(data["role"]), content=decrypt(data["content"]) or "")
            )
        return messages

    async def clear(self, conversation_id: uuid.UUID) -> None:
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.delete(self._key(conversation_id))  # type: ignore[attr-defined]

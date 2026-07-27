"""Long-term memory service (episodic / semantic / profile).

Persists durable memories with vector embeddings and recalls the most relevant
ones for a query. Memory text is encrypted at rest; embeddings are computed on
the plaintext but only the ciphertext is stored alongside the vector.

Semantic recall requires PostgreSQL/pgvector; on other backends ``recall``
returns an empty list rather than raising, so the app still functions in tests.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.repositories.repositories import (
    EmbeddingRepository,
    MemoryRepository,
)
from app.llm.router import LLMRouter
from app.models.enums import MemoryType
from app.models.memory import Memory
from app.security.crypto import decrypt, encrypt

logger = get_logger(__name__)


class MemoryService:
    def __init__(self, session: AsyncSession, router: LLMRouter) -> None:
        self.session = session
        self.router = router
        self.memories = MemoryRepository(session)
        self.embeddings = EmbeddingRepository(session)

    async def remember(
        self,
        *,
        user_id: uuid.UUID,
        content: str,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        importance: float = 0.5,
        source_ref: str | None = None,
    ) -> Memory:
        """Store a memory item plus its embedding."""
        memory = await self.memories.create(
            user_id=user_id,
            memory_type=memory_type,
            content=encrypt(content),
            importance=importance,
            source_ref=source_ref,
        )
        try:
            embedded = await self.router.embed([content], user_id=user_id)
            await self.embeddings.create(
                memory_id=memory.id,
                chunk=encrypt(content),
                chunk_index=0,
                model=embedded.model,
                vector=embedded.vectors[0],
            )
        except Exception as exc:  # noqa: BLE001 - memory still stored without vector
            logger.warning("memory.embed_failed", error=str(exc))
        return memory

    async def recall(self, *, user_id: uuid.UUID, query: str, top_k: int = 6) -> list[str]:
        """Return the most semantically-similar remembered texts (decrypted)."""
        try:
            embedded = await self.router.embed([query], user_id=user_id)
            hits = await self.embeddings.similar(embedded.vectors[0], top_k=top_k)
        except Exception as exc:  # noqa: BLE001 - e.g. non-pgvector backend
            logger.info("memory.recall_unavailable", error=str(exc))
            return []
        results: list[str] = []
        for hit in hits:
            # Only surface memories owned by this user.
            if hit.memory_id is None:
                continue
            memory = await self.memories.get(hit.memory_id)
            if memory is not None and memory.user_id == user_id:
                text = decrypt(memory.content)
                if text:
                    results.append(text)
        return results

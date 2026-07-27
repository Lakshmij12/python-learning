"""RAG retriever: turns a query into grounded context with citations.

Embeds the query, retrieves the nearest chunks from the vector store, resolves
document titles for citation, and formats a context block. Retrieved text is
sanitised (untrusted) before it is handed to the agent/LLM.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.repositories.repositories import DocumentRepository
from app.llm.router import LLMRouter
from app.rag.vectorstore import VectorStore, get_vector_store
from app.security.injection import sanitize_untrusted

logger = get_logger(__name__)


@dataclass(slots=True)
class Citation:
    text: str
    source: str
    document_id: uuid.UUID | None
    chunk_index: int


@dataclass(slots=True)
class RetrievalResult:
    context: str
    citations: list[Citation]

    @property
    def has_context(self) -> bool:
        return bool(self.citations)


class Retriever:
    def __init__(
        self,
        session: AsyncSession,
        router: LLMRouter,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.session = session
        self.router = router
        self.documents = DocumentRepository(session)
        self.store = vector_store or get_vector_store(session)

    async def retrieve(self, *, query: str, user_id: uuid.UUID, top_k: int = 6) -> RetrievalResult:
        try:
            embedded = await self.router.embed([query], user_id=user_id)
            hits = await self.store.query(embedded.vectors[0], top_k=top_k)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully (e.g. no pgvector)
            logger.info("rag.retrieve_unavailable", error=str(exc))
            return RetrievalResult(context="", citations=[])

        citations: list[Citation] = []
        for hit in hits:
            source = "document"
            if hit.document_id is not None:
                doc = await self.documents.get(hit.document_id)
                if doc is not None:
                    if doc.user_id != user_id:
                        continue  # never leak another user's document
                    source = doc.title
            citations.append(
                Citation(
                    text=sanitize_untrusted(hit.chunk),
                    source=source,
                    document_id=hit.document_id,
                    chunk_index=hit.chunk_index,
                )
            )

        context = "\n\n".join(f"[{i + 1}] ({c.source}) {c.text}" for i, c in enumerate(citations))
        return RetrievalResult(context=context, citations=citations)

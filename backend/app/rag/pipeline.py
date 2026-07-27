"""Document ingestion pipeline: chunk -> embed -> store.

Takes a persisted ``Document`` whose ``extracted_text`` has been populated
(by an upstream PDF/OCR/text extractor), splits it into chunks, embeds each via
the LLM router, and upserts them into the vector store. Updates the document's
status so the dashboard can reflect indexing progress/errors.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.repositories.repositories import DocumentRepository
from app.llm.router import LLMRouter
from app.models.enums import DocumentStatus
from app.rag.chunker import chunk_text
from app.rag.vectorstore import VectorStore, get_vector_store
from app.security.crypto import decrypt

logger = get_logger(__name__)


class RagPipeline:
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

    async def index_document(self, *, document_id: uuid.UUID, user_id: uuid.UUID) -> int:
        """Chunk, embed, and store a document. Returns the chunk count."""
        document = await self.documents.get(document_id)
        if document is None:
            return 0
        text = decrypt(document.extracted_text) if document.extracted_text else None
        if not text:
            await self.documents.update(document, status=DocumentStatus.FAILED, error="No text.")
            return 0

        await self.documents.update(document, status=DocumentStatus.PROCESSING, error=None)
        try:
            chunks = chunk_text(text)
            if chunks:
                embedded = await self.router.embed([c.text for c in chunks], user_id=user_id)
                for chunk, vector in zip(chunks, embedded.vectors, strict=True):
                    await self.store.upsert(
                        document_id=document.id,
                        chunk=chunk.text,
                        chunk_index=chunk.index,
                        model=embedded.model,
                        vector=vector,
                    )
            await self.documents.update(document, status=DocumentStatus.INDEXED)
            return len(chunks)
        except Exception as exc:  # noqa: BLE001
            logger.error("rag.index_failed", document_id=str(document_id), error=str(exc))
            await self.documents.update(document, status=DocumentStatus.FAILED, error=str(exc))
            raise

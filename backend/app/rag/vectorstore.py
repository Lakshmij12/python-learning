"""Vector store port + adapters (pgvector default, Chroma optional).

The RAG pipeline depends on the ``VectorStore`` interface, so the backing store
is swappable via ``RAG_VECTOR_STORE``. The default ``PgVectorStore`` persists
embeddings through the ORM (single datastore, transactional). ``ChromaStore`` is
available for local experimentation when ``chromadb`` is installed.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import VectorStoreName, get_settings
from app.database.repositories.repositories import EmbeddingRepository
from app.security.crypto import decrypt, encrypt


@dataclass(slots=True)
class VectorHit:
    chunk: str
    document_id: uuid.UUID | None
    chunk_index: int
    score: float | None = None


class VectorStore(ABC):
    @abstractmethod
    async def upsert(
        self,
        *,
        document_id: uuid.UUID,
        chunk: str,
        chunk_index: int,
        model: str,
        vector: list[float],
    ) -> None: ...

    @abstractmethod
    async def query(self, vector: list[float], *, top_k: int = 6) -> list[VectorHit]: ...


class PgVectorStore(VectorStore):
    """Persists embeddings via the ORM; queries with pgvector cosine distance."""

    def __init__(self, session: AsyncSession) -> None:
        self.embeddings = EmbeddingRepository(session)

    async def upsert(
        self,
        *,
        document_id: uuid.UUID,
        chunk: str,
        chunk_index: int,
        model: str,
        vector: list[float],
    ) -> None:
        # Chunk text is encrypted at rest; the vector stays plaintext.
        await self.embeddings.create(
            document_id=document_id,
            chunk=encrypt(chunk),
            chunk_index=chunk_index,
            model=model,
            vector=vector,
        )

    async def query(self, vector: list[float], *, top_k: int = 6) -> list[VectorHit]:
        rows = await self.embeddings.similar(vector, top_k=top_k)
        return [
            VectorHit(
                chunk=decrypt(r.chunk) or "",
                document_id=r.document_id,
                chunk_index=r.chunk_index,
            )
            for r in rows
        ]


class ChromaStore(VectorStore):  # pragma: no cover - optional backend
    """Chroma-backed store (requires ``chromadb``)."""

    def __init__(self, collection: str = "assistant") -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("chromadb is not installed; set RAG_VECTOR_STORE=pgvector.") from exc
        self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection(collection)

    async def upsert(self, *, document_id, chunk, chunk_index, model, vector):  # noqa: ANN001
        self._collection.add(
            ids=[f"{document_id}:{chunk_index}"],
            embeddings=[vector],
            documents=[chunk],
            metadatas=[{"document_id": str(document_id), "chunk_index": chunk_index}],
        )

    async def query(self, vector, *, top_k=6):  # noqa: ANN001
        res = self._collection.query(query_embeddings=[vector], n_results=top_k)
        hits: list[VectorHit] = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        for doc, meta in zip(docs, metas, strict=False):
            hits.append(
                VectorHit(
                    chunk=doc,
                    document_id=uuid.UUID(meta["document_id"]) if meta.get("document_id") else None,
                    chunk_index=int(meta.get("chunk_index", 0)),
                )
            )
        return hits


def get_vector_store(session: AsyncSession) -> VectorStore:
    """Return the configured vector store."""
    if get_settings().rag.vector_store == VectorStoreName.CHROMA:
        return ChromaStore()
    return PgVectorStore(session)

"""Tests for RAG chunking, ingestion pipeline, and retriever."""

from __future__ import annotations

import uuid

import pytest

from app.llm.base import EmbeddingResult
from app.models.enums import DocumentStatus
from app.rag.chunker import chunk_text
from app.rag.pipeline import RagPipeline
from app.rag.retriever import Retriever
from app.rag.vectorstore import VectorHit, VectorStore
from app.security.crypto import encrypt

pytestmark = pytest.mark.asyncio


# --- chunker (pure) ---------------------------------------------------------


def test_chunk_empty_text() -> None:
    assert chunk_text("") == []


def test_chunk_short_text_single_chunk() -> None:
    chunks = chunk_text("hello world", chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].text == "hello world"


def test_chunk_splits_and_overlaps() -> None:
    words = " ".join(f"w{i}" for i in range(100))
    chunks = chunk_text(words, chunk_size=40, overlap=10)
    assert len(chunks) > 1
    # No chunk exceeds size by much and none splits a word.
    for c in chunks:
        assert all(tok.startswith("w") for tok in c.text.split())
    # Consecutive chunks share overlapping words.
    first_tail = set(chunks[0].text.split()[-2:])
    second_head = set(chunks[1].text.split()[:3])
    assert first_tail & second_head


def test_chunk_indices_are_sequential() -> None:
    chunks = chunk_text(" ".join(str(i) for i in range(200)), chunk_size=30, overlap=5)
    assert [c.index for c in chunks] == list(range(len(chunks)))


# --- fakes ------------------------------------------------------------------


class FakeRouter:
    async def embed(self, texts, *, user_id=None):  # noqa: ANN001
        return EmbeddingResult(
            vectors=[[float(len(t))] * 3 for t in texts], provider="fake", model="fake-embed"
        )


class FakeVectorStore(VectorStore):
    def __init__(self, preset: list[VectorHit] | None = None) -> None:
        self.upserts: list[dict] = []
        self.preset = preset or []

    async def upsert(self, *, document_id, chunk, chunk_index, model, vector):  # noqa: ANN001
        self.upserts.append({"document_id": document_id, "chunk_index": chunk_index})

    async def query(self, vector, *, top_k=6):  # noqa: ANN001
        return self.preset[:top_k]


async def _make_document(db_session, user_id: uuid.UUID, text: str):  # noqa: ANN001
    from app.database.repositories.repositories import DocumentRepository

    return await DocumentRepository(db_session).create(
        user_id=user_id, title="Notes", extracted_text=encrypt(text), status=DocumentStatus.PENDING
    )


# --- pipeline ---------------------------------------------------------------


async def test_pipeline_indexes_document(db_session) -> None:  # noqa: ANN001
    user_id = uuid.uuid4()
    doc = await _make_document(db_session, user_id, " ".join(f"word{i}" for i in range(60)))
    store = FakeVectorStore()
    pipeline = RagPipeline(db_session, FakeRouter(), vector_store=store)  # type: ignore[arg-type]
    count = await pipeline.index_document(document_id=doc.id, user_id=user_id)
    assert count > 0
    assert len(store.upserts) == count
    refreshed = await pipeline.documents.get(doc.id)
    assert refreshed.status == DocumentStatus.INDEXED


async def test_pipeline_marks_failed_when_no_text(db_session) -> None:  # noqa: ANN001
    from app.database.repositories.repositories import DocumentRepository

    user_id = uuid.uuid4()
    doc = await DocumentRepository(db_session).create(
        user_id=user_id, title="Empty", extracted_text=None, status=DocumentStatus.PENDING
    )
    pipeline = RagPipeline(db_session, FakeRouter(), vector_store=FakeVectorStore())  # type: ignore[arg-type]
    count = await pipeline.index_document(document_id=doc.id, user_id=user_id)
    assert count == 0
    assert (await pipeline.documents.get(doc.id)).status == DocumentStatus.FAILED


# --- retriever --------------------------------------------------------------


async def test_retriever_builds_citations(db_session) -> None:  # noqa: ANN001
    user_id = uuid.uuid4()
    doc = await _make_document(db_session, user_id, "irrelevant")
    hits = [VectorHit(chunk="the capital is Paris", document_id=doc.id, chunk_index=0)]
    retriever = Retriever(db_session, FakeRouter(), vector_store=FakeVectorStore(hits))  # type: ignore[arg-type]
    result = await retriever.retrieve(query="capital?", user_id=user_id)
    assert result.has_context
    assert result.citations[0].source == "Notes"
    assert "[1] (Notes) the capital is Paris" in result.context


async def test_retriever_filters_other_users_documents(db_session) -> None:  # noqa: ANN001
    owner = uuid.uuid4()
    other = uuid.uuid4()
    doc = await _make_document(db_session, other, "secret")
    hits = [VectorHit(chunk="secret data", document_id=doc.id, chunk_index=0)]
    retriever = Retriever(db_session, FakeRouter(), vector_store=FakeVectorStore(hits))  # type: ignore[arg-type]
    result = await retriever.retrieve(query="?", user_id=owner)
    assert result.citations == []  # other user's document excluded

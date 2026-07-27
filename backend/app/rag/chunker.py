"""Text chunking for RAG.

Splits documents into overlapping, word-boundary-aligned chunks so retrieval
returns coherent passages. Deterministic and dependency-free (easy to test).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import get_settings


@dataclass(slots=True)
class Chunk:
    index: int
    text: str


def chunk_text(
    text: str,
    *,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Split ``text`` into overlapping chunks of roughly ``chunk_size`` chars.

    Chunks break on whitespace (never mid-word). ``overlap`` characters of the
    previous chunk's tail are prepended to the next chunk to preserve context.
    """
    settings = get_settings().rag
    size = chunk_size or settings.chunk_size
    over = overlap if overlap is not None else settings.chunk_overlap
    if size <= 0:
        raise ValueError("chunk_size must be positive")
    over = max(0, min(over, size - 1))

    words = text.split()
    if not words:
        return []

    chunks: list[Chunk] = []
    current: list[str] = []
    current_len = 0
    index = 0

    for word in words:
        # +1 accounts for the joining space.
        addition = len(word) + (1 if current else 0)
        if current_len + addition > size and current:
            chunk_str = " ".join(current)
            chunks.append(Chunk(index=index, text=chunk_str))
            index += 1
            # Seed the next chunk with the overlap tail.
            current, current_len = _overlap_tail(chunk_str, over)
        current.append(word)
        current_len += addition if current_len else len(word)

    if current:
        chunks.append(Chunk(index=index, text=" ".join(current)))
    return chunks


def _overlap_tail(chunk_str: str, overlap: int) -> tuple[list[str], int]:
    """Return the tail words of a chunk that fit within ``overlap`` chars."""
    if overlap <= 0:
        return [], 0
    tail_words: list[str] = []
    length = 0
    for word in reversed(chunk_str.split()):
        addition = len(word) + (1 if tail_words else 0)
        if length + addition > overlap:
            break
        tail_words.insert(0, word)
        length += addition
    return tail_words, length

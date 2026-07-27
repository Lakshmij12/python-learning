"""Note CRUD router. Note bodies are encrypted at rest and decrypted on read."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import CurrentUser
from app.core.exceptions import NotFoundError
from app.database.repositories.repositories import NoteRepository
from app.database.session import get_db
from app.schemas.productivity import NoteCreate, NoteResponse
from app.security.crypto import decrypt, encrypt

router = APIRouter(prefix="/notes", tags=["notes"])


def _to_response(note) -> NoteResponse:  # noqa: ANN001
    return NoteResponse(
        id=note.id,
        title=note.title,
        content=decrypt(note.content) or "",
        created_at=note.created_at,
    )


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NoteResponse:
    note = await NoteRepository(db).create(
        user_id=user.id, title=payload.title, content=encrypt(payload.content)
    )
    return _to_response(note)


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[NoteResponse]:
    notes = await NoteRepository(db).list(user_id=user.id, limit=limit, offset=offset)
    return [_to_response(n) for n in notes]


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    repo = NoteRepository(db)
    note = await repo.get(note_id)
    if note is None or note.user_id != user.id:
        raise NotFoundError("Note not found.")
    await repo.delete(note)

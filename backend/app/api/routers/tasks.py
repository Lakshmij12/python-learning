"""Task CRUD router (dashboard + API)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import CurrentUser
from app.core.exceptions import NotFoundError
from app.database.repositories.repositories import TaskRepository
from app.database.session import get_db
from app.schemas.productivity import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    task = await TaskRepository(db).create(
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_at=payload.due_at,
    )
    return TaskResponse.model_validate(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[TaskResponse]:
    tasks = await TaskRepository(db).list(user_id=user.id, limit=limit, offset=offset)
    return [TaskResponse.model_validate(t) for t in tasks]


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None or task.user_id != user.id:
        raise NotFoundError("Task not found.")
    changes = payload.model_dump(exclude_unset=True)
    task = await repo.update(task, **changes)
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None or task.user_id != user.id:
        raise NotFoundError("Task not found.")
    await repo.delete(task)

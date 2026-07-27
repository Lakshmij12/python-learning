"""Authentication dependencies for FastAPI routes.

Supports two credential types:
* **Bearer JWT** (dashboard user sessions), and
* **API key** via the ``X-API-Key`` header (programmatic access).

``get_current_user`` resolves either into the authenticated :class:`User`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.database.repositories.repositories import ApiKeyRepository, UserRepository
from app.database.session import get_db
from app.models.user import User
from app.security import tokens
from app.utils.time import ensure_aware

# auto_error=False so we can also accept an API key when no bearer is present.
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    """Resolve the authenticated user from a JWT or API key."""
    if credentials is not None:
        return await _user_from_jwt(db, credentials.credentials)
    if x_api_key:
        return await _user_from_api_key(db, x_api_key)
    raise AuthenticationError("Missing credentials.")


async def get_current_active_superuser(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require an active superuser (dashboard admin operations)."""
    if not user.is_active or not user.is_superuser:
        raise AuthorizationError()
    return user


async def _user_from_jwt(db: AsyncSession, token: str) -> User:
    claims = tokens.decode_access_token(token)
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Malformed token subject.") from exc
    user = await UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive.")
    return user


async def _user_from_api_key(db: AsyncSession, raw_key: str) -> User:
    repo = ApiKeyRepository(db)
    api_key = await repo.get_by_key_hash(tokens.hash_token(raw_key))
    now = datetime.now(timezone.utc)
    expires = ensure_aware(api_key.expires_at) if api_key else None
    if api_key is None or (expires is not None and expires < now):
        raise AuthenticationError("Invalid or expired API key.")
    await repo.update(api_key, last_used_at=now)
    user = await UserRepository(db).get(api_key.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

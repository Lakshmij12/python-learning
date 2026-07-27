"""Authentication router: register, login, refresh, logout, me."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import CurrentUser
from app.database.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return ua, ip


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Create the account owner (intended for first-run setup)."""
    user = await AuthService(db).register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        whatsapp_number=payload.whatsapp_number,
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Exchange credentials for an access/refresh token pair."""
    ua, ip = _client_meta(request)
    pair = await AuthService(db).authenticate(
        email=payload.email, password=payload.password, user_agent=ua, ip=ip
    )
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Rotate a refresh token for a fresh access/refresh pair."""
    pair = await AuthService(db).refresh(refresh_token=payload.refresh_token)
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Revoke the presented refresh-token session."""
    await AuthService(db).logout(refresh_token=payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse.model_validate(current_user)

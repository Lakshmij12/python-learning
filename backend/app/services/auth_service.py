"""Authentication use-cases: register, login, refresh, logout.

Encapsulates all auth business logic so routers stay thin. Depends only on
repositories and the security primitives, keeping it unit-testable without HTTP.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.logging import get_logger
from app.database.repositories.repositories import (
    SessionRepository,
    UserRepository,
)
from app.models.enums import AuditAction
from app.models.system import AuditLog
from app.models.user import User
from app.security import passwords, tokens
from app.utils.time import ensure_aware

logger = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)

    # --- registration ------------------------------------------------------

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None = None,
        whatsapp_number: str | None = None,
    ) -> User:
        """Create the account owner. Fails if the email already exists."""
        if await self.users.get_by_email(email):
            raise ConflictError("An account with this email already exists.")
        user = await self.users.create(
            email=email.lower(),
            password_hash=passwords.hash_password(password),
            full_name=full_name,
            whatsapp_number=whatsapp_number,
        )
        await self._audit(user.id, AuditAction.CREATE, "user", str(user.id))
        return user

    # --- login -------------------------------------------------------------

    async def authenticate(
        self, *, email: str, password: str, user_agent: str | None, ip: str | None
    ) -> tokens.TokenPair:
        """Verify credentials and issue an access/refresh token pair."""
        user = await self.users.get_by_email(email)
        # Verify even when the user is missing to reduce timing side channels.
        stored_hash = user.password_hash if user else _DUMMY_HASH
        valid = passwords.verify_password(password, stored_hash)
        if not user or not valid or not user.is_active:
            raise AuthenticationError("Invalid email or password.")

        # Transparent hash upgrade if parameters changed.
        if passwords.needs_rehash(user.password_hash):
            await self.users.update(user, password_hash=passwords.hash_password(password))

        pair = await self._issue_pair(user, user_agent=user_agent, ip=ip)
        await self.users.update(user, last_login_at=datetime.now(UTC))
        await self._audit(user.id, AuditAction.LOGIN, "user", str(user.id), ip=ip)
        return pair

    # --- refresh -----------------------------------------------------------

    async def refresh(self, *, refresh_token: str) -> tokens.TokenPair:
        """Rotate a refresh token: validate, revoke old, issue a new pair."""
        token_hash = tokens.hash_token(refresh_token)
        session = await self.sessions.get_by_refresh_hash(token_hash)
        now = datetime.now(UTC)
        if session is None or ensure_aware(session.expires_at) < now:
            raise AuthenticationError("Invalid or expired refresh token.")

        user = await self.users.get(session.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Account is not active.")

        # Rotate: revoke the presented token before issuing a replacement.
        await self.sessions.update(session, revoked_at=now)
        return await self._issue_pair(user, user_agent=session.user_agent, ip=session.ip_address)

    # --- logout ------------------------------------------------------------

    async def logout(self, *, refresh_token: str) -> None:
        """Revoke a single session (per-device logout)."""
        session = await self.sessions.get_by_refresh_hash(tokens.hash_token(refresh_token))
        if session is not None:
            await self.sessions.update(session, revoked_at=datetime.now(UTC))
            await self._audit(session.user_id, AuditAction.LOGOUT, "session", str(session.id))

    # --- helpers -----------------------------------------------------------

    async def _issue_pair(
        self, user: User, *, user_agent: str | None, ip: str | None
    ) -> tokens.TokenPair:
        raw_refresh, refresh_hash = tokens.generate_refresh_token()
        await self.sessions.create(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            user_agent=user_agent,
            ip_address=ip,
            expires_at=tokens.refresh_expiry(),
        )
        access = tokens.create_access_token(user.id)
        from app.config.settings import get_settings

        ttl = get_settings().security.access_token_ttl_minutes * 60
        return tokens.TokenPair(access_token=access, refresh_token=raw_refresh, expires_in=ttl)

    async def _audit(
        self,
        user_id: uuid.UUID | None,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        *,
        ip: str | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip,
                occurred_at=datetime.now(UTC),
            )
        )
        await self.session.flush()


# A valid Argon2 hash of a random value, used to equalise timing when the user
# does not exist (mitigates user-enumeration via response time).
_DUMMY_HASH = passwords.hash_password("timing-equaliser-not-a-real-password")

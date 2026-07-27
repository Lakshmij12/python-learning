"""JWT issuance/verification and opaque-token hashing.

* **Access tokens** are short-lived signed JWTs carrying the user id (``sub``).
* **Refresh tokens** are long random opaque strings; only their SHA-256 hash is
  stored (``sessions.refresh_token_hash``), enabling per-device revocation.
* **API keys** follow the same hash-at-rest pattern with a visible prefix.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config.settings import get_settings
from app.core.exceptions import AuthenticationError

_ACCESS = "access"  # noqa: S105 - token *type* label, not a secret
_REFRESH = "refresh"  # noqa: S105


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int  # access-token lifetime, seconds


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: uuid.UUID, *, extra: dict[str, Any] | None = None) -> str:
    """Issue a signed short-lived access token."""
    settings = get_settings().security
    now = _now()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": _ACCESS,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_ttl_minutes)).timestamp()),
        "jti": secrets.token_urlsafe(8),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify signature/expiry and return the claims. Raises on any problem."""
    settings = get_settings().security
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Access token expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid access token.") from exc
    if claims.get("type") != _ACCESS:
        raise AuthenticationError("Wrong token type.")
    return claims


def generate_refresh_token() -> tuple[str, str]:
    """Return ``(raw_token, sha256_hash)``. Store only the hash."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    """SHA-256 hex digest used for refresh tokens and API keys at rest."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return ``(raw_key, prefix, sha256_hash)`` for a new API key.

    The raw key is shown to the user exactly once; only prefix + hash persist.
    """
    body = secrets.token_urlsafe(32)
    prefix = f"wa_{secrets.token_hex(3)}"
    raw = f"{prefix}.{body}"
    return raw, prefix, hash_token(raw)


def refresh_expiry() -> datetime:
    return _now() + timedelta(days=get_settings().security.refresh_token_ttl_days)

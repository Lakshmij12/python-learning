"""Password hashing using Argon2id (memory-hard, modern default)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# Argon2id with library defaults (tuned, safe). Parameters are embedded in the
# hash string, so ``needs_rehash`` can transparently upgrade cost over time.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an Argon2id hash of ``password``."""
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time verify. Returns ``False`` on any mismatch/invalid hash."""
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(hashed: str) -> bool:
    """Whether ``hashed`` should be re-hashed with current parameters."""
    try:
        return _hasher.check_needs_rehash(hashed)
    except (InvalidHashError, ValueError):
        return True

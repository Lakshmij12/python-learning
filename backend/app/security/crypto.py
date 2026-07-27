"""Application-layer field encryption (AES-256-GCM).

Sensitive columns (message bodies, notes, memory, extracted document text) are
encrypted before they touch the database. AES-256-GCM provides authenticated
encryption: any tampering with the ciphertext is detected on decrypt.

Envelope format (all base64url, ``.``-joined)::

    v1.<nonce>.<ciphertext+tag>

The version prefix allows key rotation / algorithm migration later.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config.settings import Settings, get_settings
from app.core.exceptions import ConfigurationError

_VERSION = "v1"
_NONCE_BYTES = 12  # 96-bit nonce recommended for GCM


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("ascii"))


class Cipher:
    """AES-256-GCM cipher bound to a 32-byte key."""

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ConfigurationError("Encryption key must be exactly 32 bytes (AES-256).")
        self._aead = AESGCM(key)

    def encrypt(self, plaintext: str, *, aad: bytes | None = None) -> str:
        """Encrypt a UTF-8 string, returning the versioned envelope."""
        nonce = os.urandom(_NONCE_BYTES)
        ct = self._aead.encrypt(nonce, plaintext.encode("utf-8"), aad)
        return f"{_VERSION}.{_b64e(nonce)}.{_b64e(ct)}"

    def decrypt(self, envelope: str, *, aad: bytes | None = None) -> str:
        """Decrypt a versioned envelope back to the original string."""
        try:
            version, nonce_b64, ct_b64 = envelope.split(".", 2)
        except ValueError as exc:  # malformed
            raise ConfigurationError("Malformed ciphertext envelope.") from exc
        if version != _VERSION:
            raise ConfigurationError(f"Unsupported ciphertext version: {version!r}")
        try:
            plaintext = self._aead.decrypt(_b64d(nonce_b64), _b64d(ct_b64), aad)
        except InvalidTag as exc:  # tampering or wrong key
            raise ConfigurationError("Ciphertext authentication failed.") from exc
        return plaintext.decode("utf-8")


def _load_key(settings: Settings) -> bytes:
    """Resolve the AES key from settings.

    Production requires a real base64-encoded 32-byte key. In ``local`` an
    ephemeral key is generated so the app runs without configuration (data
    encrypted in one run cannot be decrypted after restart — dev only).
    """
    raw = settings.security.encryption_key.get_secret_value()
    if raw:
        try:
            key = base64.b64decode(raw)
        except Exception as exc:  # noqa: BLE001
            raise ConfigurationError("SECURITY_ENCRYPTION_KEY must be base64.") from exc
        if len(key) != 32:
            raise ConfigurationError("SECURITY_ENCRYPTION_KEY must decode to 32 bytes.")
        return key
    if settings.app.is_production:
        raise ConfigurationError("SECURITY_ENCRYPTION_KEY is required in production.")
    return os.urandom(32)  # ephemeral dev key


_cipher: Cipher | None = None


def get_cipher() -> Cipher:
    """Return the process-wide cipher singleton."""
    global _cipher
    if _cipher is None:
        _cipher = Cipher(_load_key(get_settings()))
    return _cipher


def encrypt(plaintext: str | None) -> str | None:
    """Encrypt, passing through ``None`` (nullable columns)."""
    return None if plaintext is None else get_cipher().encrypt(plaintext)


def decrypt(envelope: str | None) -> str | None:
    """Decrypt, passing through ``None``."""
    return None if envelope is None else get_cipher().decrypt(envelope)

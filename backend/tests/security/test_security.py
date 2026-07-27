"""Security tests: crypto, passwords, tokens."""

from __future__ import annotations

import base64
import os

import pytest

from app.core.exceptions import AuthenticationError, ConfigurationError
from app.security import passwords, tokens
from app.security.crypto import Cipher


@pytest.fixture
def cipher() -> Cipher:
    return Cipher(os.urandom(32))


# --- AES-256-GCM ------------------------------------------------------------


def test_encrypt_roundtrip(cipher: Cipher) -> None:
    ct = cipher.encrypt("secret message 🤫")
    assert ct.startswith("v1.")
    assert cipher.decrypt(ct) == "secret message 🤫"


def test_ciphertext_is_nondeterministic(cipher: Cipher) -> None:
    assert cipher.encrypt("same") != cipher.encrypt("same")  # random nonce


def test_tampering_is_detected(cipher: Cipher) -> None:
    ct = cipher.encrypt("important")
    version, nonce, body = ct.split(".", 2)
    flipped = bytearray(base64.urlsafe_b64decode(body))
    flipped[0] ^= 0x01
    tampered = f"{version}.{nonce}.{base64.urlsafe_b64encode(bytes(flipped)).decode()}"
    with pytest.raises(ConfigurationError):
        cipher.decrypt(tampered)


def test_wrong_key_cannot_decrypt() -> None:
    ct = Cipher(os.urandom(32)).encrypt("data")
    with pytest.raises(ConfigurationError):
        Cipher(os.urandom(32)).decrypt(ct)


def test_key_must_be_32_bytes() -> None:
    with pytest.raises(ConfigurationError):
        Cipher(os.urandom(16))


# --- passwords --------------------------------------------------------------


def test_password_hash_and_verify() -> None:
    h = passwords.hash_password("CorrectHorseBattery")
    assert h != "CorrectHorseBattery"
    assert passwords.verify_password("CorrectHorseBattery", h)
    assert not passwords.verify_password("wrong", h)


def test_verify_bad_hash_returns_false() -> None:
    assert passwords.verify_password("x", "not-a-hash") is False


# --- tokens -----------------------------------------------------------------


def test_access_token_roundtrip() -> None:
    import uuid

    uid = uuid.uuid4()
    token = tokens.create_access_token(uid)
    claims = tokens.decode_access_token(token)
    assert claims["sub"] == str(uid)
    assert claims["type"] == "access"


def test_tampered_jwt_rejected() -> None:
    import uuid

    token = tokens.create_access_token(uuid.uuid4())
    with pytest.raises(AuthenticationError):
        tokens.decode_access_token(token + "x")


def test_refresh_token_only_hash_stored() -> None:
    raw, digest = tokens.generate_refresh_token()
    assert raw != digest
    assert tokens.hash_token(raw) == digest
    assert len(digest) == 64  # sha256 hex


def test_api_key_prefix_and_hash() -> None:
    raw, prefix, digest = tokens.generate_api_key()
    assert raw.startswith(prefix)
    assert tokens.hash_token(raw) == digest

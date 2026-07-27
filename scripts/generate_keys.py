#!/usr/bin/env python3
"""Generate strong secrets for the WhatsApp AI Assistant.

Prints ready-to-paste values for the secret-bearing environment variables.
Uses the OS CSPRNG (``secrets`` module) only — never a predictable PRNG.

Usage
-----
    python scripts/generate_keys.py

Then copy the printed lines into your `.env` (never commit real secrets).
"""

from __future__ import annotations

import base64
import secrets


def _urlsafe_token(nbytes: int = 48) -> str:
    """Return a URL-safe random token suitable for JWT/verify tokens."""
    return secrets.token_urlsafe(nbytes)


def _aes256_key_b64() -> str:
    """Return a base64-encoded 32-byte (256-bit) key for AES-256-GCM."""
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def main() -> None:
    print("# --- Generated secrets (paste into .env) ---")
    print(f"SECURITY_JWT_SECRET={_urlsafe_token()}")
    print(f"SECURITY_ENCRYPTION_KEY={_aes256_key_b64()}")
    print(f"WHATSAPP_VERIFY_TOKEN={_urlsafe_token(24)}")
    print("# WHATSAPP_APP_SECRET comes from the Meta App dashboard (do not generate).")


if __name__ == "__main__":
    main()

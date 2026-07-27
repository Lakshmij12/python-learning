# Security Guide

Security is layered throughout the stack. This document summarises the controls
and where they live in the code.

## Data protection

- **Encryption at rest (AES-256-GCM)** — message bodies, notes, memory, and
  extracted document text are encrypted at the application layer
  (`app/security/crypto.py`). Authenticated encryption detects tampering; a
  versioned envelope (`v1.<nonce>.<ct>`) supports key rotation.
- **Key management** — the 32-byte key comes from `SECURITY_ENCRYPTION_KEY`
  (base64). Generate with `scripts/generate_keys.py`. Production refuses to boot
  without a real key.
- **Secrets never logged** — `SecretStr` masks values in config; the structlog
  redaction processor scrubs sensitive keys and secret-like text
  (`app/core/logging.py`).

## Authentication & authorization

- **Passwords**: Argon2id with transparent rehash (`app/security/passwords.py`).
- **JWT access tokens** + **rotating refresh tokens** stored only as SHA-256
  hashes for per-device revocation (`app/security/tokens.py`,
  `services/auth_service.py`).
- **API keys**: visible prefix + hashed secret, with expiry/rotation.
- **Timing-equalised login** to resist user enumeration.
- **Per-resource ownership checks** on every API route.

## Webhook security

- **HMAC verification** of `X-Hub-Signature-256` on every event using the Meta
  app secret (`messaging/providers/cloud_api.py`).
- **Replay protection**: timestamp freshness window + Redis `SET NX`
  idempotency, backed by a DB unique constraint (`messaging/replay.py`).
- **Owner-only ingestion**: only the configured owner number is processed
  (`services/ingestion_service.py`) — a privacy guarantee.

## LLM / prompt-injection defence

- **Injection heuristics** on inbound text and on retrieved/stored content
  (`app/security/injection.py`); the agent refuses obvious jailbreak attempts.
- **Untrusted-content sanitisation** (fake role-tag stripping, length clamps)
  before context injection.
- **Per-user RAG isolation** — retrieval never surfaces another user's document.

## Transport & headers

- TLS terminated at Nginx; HSTS over HTTPS.
- Security headers on every response (`middleware/security_headers.py`):
  `X-Content-Type-Options`, `X-Frame-Options: DENY`, strict CSP, `Referrer-
  Policy`, `Permissions-Policy`.
- **CORS** restricted to configured dashboard origins.

## Availability

- **Rate limiting** (Redis fixed-window) with fail-open on cache outage
  (`middleware/rate_limit.py`), plus Nginx edge limits.

## Auditing

- Security-relevant actions (login/logout, create/update/delete, export, purge,
  webhook, LLM calls) recorded in `audit_logs`.

## Supply chain

- CI runs **bandit** (SAST), **pip-audit** (dependency CVEs), and **gitleaks**
  (secret scanning). Dependencies are pinned by lower bounds; use a lockfile in
  production.

## Reporting

Report vulnerabilities privately to the repository owner. Do not open public
issues for security reports.

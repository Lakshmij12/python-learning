# Testing Guide

The suite is layered to match the architecture and runs without any external
services (an in-memory async SQLite database stands in for PostgreSQL, and
Redis/LLM/messaging providers are faked or degrade gracefully).

## Layout

| Suite | Path | What it covers |
|---|---|---|
| Unit | `tests/unit` | config, models/repositories, messaging parse/verify, LLM router fallback, memory, RAG chunker/pipeline/retriever |
| Integration | `tests/integration` | auth service, ingestion, agent orchestrator (tool-calling, injection refusal), command router |
| Security | `tests/security` | AES-256-GCM, Argon2, JWT/tokens, prompt-injection guard, webhook HMAC over HTTP |
| API | `tests/api` | full ASGI flow: health, register/login/me, task CRUD, webhook handshake, security headers |
| Performance | `tests/performance` | crypto throughput, chunker scaling (marked `performance`) |

## Running

```bash
cd backend

# everything (with coverage — configured in pyproject.toml)
pytest

# a single layer
pytest tests/unit -o addopts=""

# skip performance tests
pytest -m "not performance"

# only security tests
pytest -m security   # or: pytest tests/security
```

## Fixtures

- `tests/conftest.py` — `db_session`: fresh in-memory async SQLite session.
- API tests build the real app and override `get_db` with a `StaticPool`
  in-memory database shared across connections.

## Determinism notes

- Timestamps are set explicitly where ordering is asserted (SQLite
  `CURRENT_TIMESTAMP` is second-resolution).
- Vector similarity requires PostgreSQL/pgvector; on SQLite those paths degrade
  to empty results, which the tests assert.
- `get_settings.cache_clear()` is called around env-var overrides.

## Coverage

Current line coverage is ~71%. Untested paths are mainly live provider HTTP
calls (require real API keys) and the optional Chroma backend; these are covered
by integration testing against real services in a staging environment.

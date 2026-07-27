# Database Guide

PostgreSQL (with the **pgvector** extension) accessed via **async SQLAlchemy
2.0**. Migrations are managed by **Alembic**.

## Schema (17 tables)

| Domain | Tables |
|---|---|
| Auth | `users`, `sessions`, `api_keys` |
| Messaging | `conversations`, `messages` |
| Memory / RAG | `memory`, `embeddings`, `documents`, `files` |
| Productivity | `tasks`, `notes`, `reminders` |
| System | `settings`, `prompts`, `llm_usage`, `logs`, `audit_logs` |

### Conventions

- **UUID primary keys** (`UUIDMixin`) generated application-side — native
  `UUID` on Postgres, `CHAR(32)` under SQLite in tests.
- **Timestamps** (`TimestampMixin`): `created_at` / `updated_at` maintained by
  the database.
- **Soft delete** (`SoftDeleteMixin`): `deleted_at` supports GDPR-style erasure
  and full export; repositories exclude soft-deleted rows by default.
- **Encryption at rest**: message/note/memory/document text columns hold
  AES-256-GCM ciphertext; plaintext exists only in memory during processing.
- **JSON**: `JSONB` on Postgres, `JSON` elsewhere (`JSONVariant`).
- **Vectors**: `embeddings.vector` is `pgvector` on Postgres, `JSON` fallback in
  tests; an **HNSW** cosine index accelerates similarity search.

## Layers

```
Service  →  Repository (app/database/repositories)  →  AsyncSession  →  DB
```

- `BaseRepository[Model]` provides `add/create/get/list/count/update/delete`,
  soft-delete awareness, and pagination.
- Concrete repositories add model-specific queries (`get_by_email`,
  `get_or_create`, `get_by_provider_id`, `recent_for_conversation`,
  `EmbeddingRepository.similar` for ANN search, `ReminderRepository.due`).
- `get_db` (`app/database/session.py`) yields a request-scoped session with
  Unit-of-Work semantics (commit on success, rollback on error, always close).

## Migrations

```bash
cd backend

# apply latest schema (creates pgvector extension + HNSW index)
alembic upgrade head

# create a new migration after changing models
alembic revision --autogenerate -m "add X"

# roll back one step
alembic downgrade -1
```

The database URL comes from application settings (`DB_*`), so no credentials
live in `alembic.ini`. For tests/CI you can override with
`ALEMBIC_DATABASE_URL` (e.g. a SQLite URL).

## Testing

`tests/conftest.py` provides an in-memory async SQLite `db_session` fixture, so
model and repository tests run fast with no external services. Vector-similarity
tests require PostgreSQL and are marked `integration`.

```bash
python -m pytest tests/unit -o addopts=""
```

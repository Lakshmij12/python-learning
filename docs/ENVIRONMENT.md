# Environment Variable Guide

All configuration is typed and validated by `backend/app/config/settings.py`
(Pydantic Settings). Copy `.env.example` → `.env` and fill in real values.
**Never commit `.env`.** Generate secrets with `python scripts/generate_keys.py`.

Variables are grouped by prefix; each group maps to a nested settings model.

## Application (`APP_`)

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | WhatsApp AI Assistant | Display name. |
| `APP_ENVIRONMENT` | `local` | `local` \| `development` \| `staging` \| `production`. Non-`local` triggers strict secret validation at startup. |
| `APP_DEBUG` | `false` | Verbose errors. Keep `false` in production. |
| `APP_LOG_LEVEL` | `INFO` | `DEBUG`…`CRITICAL`. |
| `APP_HOST` / `APP_PORT` | `0.0.0.0` / `8000` | Bind address. |
| `APP_BASE_URL` | `http://localhost:8000` | Public URL used to build webhook/callback links. |
| `APP_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed dashboard origins. |

## Database (`DB_`)

`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, plus pool tuning
(`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_ECHO`). The async DSN
(`postgresql+asyncpg://…`) and a sync DSN for Alembic are derived automatically.

## Redis (`REDIS_`)

`REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, optional `REDIS_PASSWORD`. Used for
cache, Celery broker/result backend, rate limiting, and webhook replay guard.

## Security (`SECURITY_`)

| Variable | Notes |
|---|---|
| `SECURITY_JWT_SECRET` | **Required outside `local`.** Strong random string. |
| `SECURITY_JWT_ALGORITHM` | `HS256` (default) / `HS384` / `HS512`. |
| `SECURITY_ACCESS_TOKEN_TTL_MINUTES` | Access token lifetime (default 30). |
| `SECURITY_REFRESH_TOKEN_TTL_DAYS` | Refresh token lifetime (default 14). |
| `SECURITY_ENCRYPTION_KEY` | **Required outside `local`.** base64-encoded 32-byte AES-256-GCM key. |
| `SECURITY_RATE_LIMIT_REQUESTS` / `_WINDOW_SECONDS` | Sliding-window rate limit. |
| `SECURITY_WEBHOOK_REPLAY_WINDOW_SECONDS` | Max age (s) of accepted webhook events. |

## WhatsApp (`WHATSAPP_`) — official Cloud API

| Variable | Where it comes from |
|---|---|
| `WHATSAPP_API_VERSION` | Graph API version, e.g. `v20.0`. |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta App → WhatsApp → API setup. |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | WhatsApp Business Account ID. |
| `WHATSAPP_ACCESS_TOKEN` | Permanent system-user token (store as secret). |
| `WHATSAPP_VERIFY_TOKEN` | You choose it; used for webhook handshake. |
| `WHATSAPP_APP_SECRET` | Meta App secret; validates `X-Hub-Signature-256`. |
| `WHATSAPP_OWNER_PHONE_NUMBER` | Your number — only messages from it are processed. |

## LLM router (`LLM_`) and providers

`LLM_DEFAULT_PROVIDER` (`openai`\|`gemini`\|`claude`\|`ollama`),
`LLM_FALLBACK_PROVIDERS` (comma-separated), `LLM_REQUEST_TIMEOUT_SECONDS`,
`LLM_MAX_RETRIES`, `LLM_TEMPERATURE`, `LLM_EMBEDDING_DIMENSIONS` (must match the
embedding model).

Per provider: `OPENAI_API_KEY` / `OPENAI_CHAT_MODEL` / `OPENAI_EMBEDDING_MODEL`
(+ optional `OPENAI_BASE_URL`); `GEMINI_*`; `CLAUDE_*`; and `OLLAMA_BASE_URL` /
`OLLAMA_CHAT_MODEL` / `OLLAMA_EMBEDDING_MODEL` for fully local, private AI.

## Celery (`CELERY_`)

`CELERY_BROKER_DB`, `CELERY_RESULT_DB` (Redis DB indexes),
`CELERY_TASK_TIME_LIMIT_SECONDS`, `CELERY_TASK_SOFT_TIME_LIMIT_SECONDS`.

## RAG (`RAG_`)

`RAG_VECTOR_STORE` (`pgvector`\|`chroma`), `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP`,
`RAG_TOP_K`, `RAG_WORKING_MEMORY_TURNS`.

## Startup validation

In any non-`local` environment, the app refuses to start if `JWT_SECRET`,
`ENCRYPTION_KEY`, `WHATSAPP_APP_SECRET`, or `WHATSAPP_VERIFY_TOKEN` are missing
or left at placeholder defaults (`Settings.validate_runtime()`). This is a
deliberate fail-fast guard against shipping insecure defaults.

# Troubleshooting Guide

## Startup

**App refuses to start with a configuration error.**
In non-`local` environments the app fails fast if `SECURITY_JWT_SECRET`,
`SECURITY_ENCRYPTION_KEY`, `WHATSAPP_APP_SECRET`, or `WHATSAPP_VERIFY_TOKEN` are
missing/placeholder. Run `python scripts/generate_keys.py` and set them.

**`alembic upgrade head` fails with "type vector does not exist".**
The database must have the pgvector extension. Use the `pgvector/pgvector` image
(the initial migration runs `CREATE EXTENSION vector`), or install pgvector.

## Webhook

**Meta verification (GET) fails.**
Ensure `WHATSAPP_VERIFY_TOKEN` matches the token entered in the Meta dashboard,
and the callback URL is `https://<domain>/webhook/whatsapp`.

**Events return 403.**
Signature mismatch — confirm `WHATSAPP_APP_SECRET` is the *app secret* from the
Meta App (not the access token). The HMAC is computed over the raw body.

**Messages are received but no reply is sent.**
- Check `WHATSAPP_OWNER_PHONE_NUMBER` matches the sending number (E.164). Only
  the owner's messages are processed.
- Check the LLM provider is reachable / keys are set, or set
  `LLM_DEFAULT_PROVIDER=ollama` with Ollama running.
- Inspect `worker`/`backend` logs for `assistant.send_failed`.

## LLM

**`All LLM providers failed`.**
Every provider in the chain errored. Verify API keys and network egress; add
`LLM_FALLBACK_PROVIDERS=ollama` for a local fallback.

**Semantic recall / RAG returns nothing.**
Vector search requires PostgreSQL/pgvector. On SQLite (tests) it degrades to
empty by design. Ensure documents were indexed (status `indexed`).

## Database / cache

**`TypeError: can't compare offset-naive and offset-aware datetimes`.**
Should not occur — `app/utils/time.ensure_aware` normalises DB datetimes. If you
add new time comparisons, wrap DB values with `ensure_aware`.

**Rate limiting seems disabled.**
It fails open when Redis is unreachable (by design). Check the `redis` service
and `REDIS_HOST`.

## Tests

**`unrecognized arguments: --cov`.**
Run a single file without the configured addopts: `pytest <path> -o addopts=""`,
or install `pytest-cov` (in the `dev` extra).

**Vector similarity tests error on SQLite.**
Those paths require PostgreSQL and are marked `integration`; the default suite
asserts graceful degradation instead.

## Docker

**Backend healthcheck failing.**
`/health` must return 200. Check migrations ran (`docker compose logs backend`)
and that Postgres/Redis are healthy (`docker compose ps`).

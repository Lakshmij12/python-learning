# Deployment Guide

## Topology

`docker compose` runs the full stack:

| Service | Image / build | Role |
|---|---|---|
| `nginx` | nginx:1.27 | TLS termination, routing, edge rate limit |
| `backend` | `./backend` | FastAPI (gunicorn + uvicorn workers) |
| `worker` | `./backend` | Celery worker (OCR, embeddings, sends) |
| `beat` | `./backend` | Celery Beat (reminders, digests) |
| `postgres` | pgvector/pgvector:pg16 | database + vector search |
| `redis` | redis:7 | cache, broker, rate-limit, replay guard |
| `ollama` | ollama/ollama | local models (profile `local-ai`) |
| `frontend` | `./frontend` | Next.js dashboard |

## Prerequisites

- Docker + Docker Compose
- A **Meta App** with WhatsApp Cloud API configured (phone number id, permanent
  access token, app secret) — see the Meta Business Platform docs.
- A public HTTPS URL for the webhook (e.g. via your reverse proxy / a tunnel in
  development).

## Steps

1. **Secrets**
   ```bash
   cp .env.example .env
   python scripts/generate_keys.py     # paste JWT/encryption/verify tokens
   ```
   Fill `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`,
   `WHATSAPP_APP_SECRET`, `WHATSAPP_OWNER_PHONE_NUMBER`, and your LLM keys
   (`OPENAI_API_KEY`, …) — or set `LLM_DEFAULT_PROVIDER=ollama` for local-only.

2. **Bring up the stack**
   ```bash
   docker compose up --build -d
   docker compose logs -f backend       # watch migrations + startup
   ```
   The backend container runs `alembic upgrade head` before serving.

3. **Register the webhook** in the Meta App dashboard:
   - Callback URL: `https://<your-domain>/webhook/whatsapp`
   - Verify token: the `WHATSAPP_VERIFY_TOKEN` you set
   - Subscribe to the `messages` field.

4. **Create the owner account** (dashboard login):
   ```bash
   curl -X POST https://<your-domain>/auth/register \
     -H 'Content-Type: application/json' \
     -d '{"email":"you@example.com","password":"<strong-password>","whatsapp_number":"<E164>"}'
   ```

5. **TLS**: terminate HTTPS at Nginx (uncomment the `ssl` lines in
   `docker/nginx/nginx.conf` and mount your certs) or front the stack with a
   managed load balancer / Caddy / Traefik.

## Production notes

- Set `APP_ENVIRONMENT=production` — the app refuses to boot with placeholder
  secrets (`Settings.validate_runtime`).
- Scale API and workers independently: `docker compose up -d --scale worker=3`.
- Back up the `pgdata` volume regularly (encrypted). All sensitive columns are
  already ciphertext at rest.
- Rotate secrets by updating `.env` and restarting; API keys support rotation
  via the prefix/hash scheme.

## CI/CD

`.github/workflows/ci.yml` runs on push/PR: **lint (ruff/black) → type-check
(mypy, advisory) → tests (pytest + coverage) → security scan (bandit, pip-audit,
gitleaks) → docker build** for backend and frontend images.

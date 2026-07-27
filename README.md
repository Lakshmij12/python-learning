# AI WhatsApp Personal Assistant

A secure, privacy-first, provider-agnostic AI assistant for **your own** WhatsApp
Business number — integrated **only** through the official **WhatsApp Cloud API /
Business Platform**. Reply to messages, remember context, summarise chats, manage
tasks/notes/reminders, run RAG over your documents, and use multiple LLM
providers (OpenAI / Gemini / Claude) or fully-local **Ollama**.

> Built with privacy-by-design and security-first principles. Your messages are
> encrypted at rest, never sent to third-party telemetry, and fully
> exportable/deletable. Local-only operation is a first-class option.

## Features

- **Conversational AI** with short-term (working) + long-term (episodic /
  semantic / profile) memory and conversation summaries.
- **Agent** with planning, tool/function calling, and an injection-guarded
  reasoning loop (LangGraph-style state machine).
- **RAG** over your PDFs/notes/chats with pgvector + citations.
- **Productivity**: tasks, notes, reminders (Celery Beat), slash-commands.
- **Multi-provider LLM router** with automatic fallback and usage accounting.
- **Admin dashboard** (Next.js + Tailwind).
- **Security**: AES-256-GCM field encryption, Argon2 passwords, JWT/OAuth2,
  HMAC-verified webhooks with replay protection, rate limiting, audit logs.

## Architecture

```
WhatsApp Cloud API → Nginx → FastAPI (webhook verify → ingest → agent → reply)
                                   │
              services · agents · memory · rag · llm-router · messaging
                                   │
                PostgreSQL+pgvector · Redis · Celery workers · Ollama
Dashboard: Next.js  ─────────────► FastAPI REST (JWT/OAuth2)
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

## Tech stack

Python 3.12 · FastAPI · SQLAlchemy 2 (async) · PostgreSQL + pgvector · Redis ·
Celery · Pydantic · structlog · httpx · Next.js 14 · TailwindCSS · Docker ·
GitHub Actions.

## Quick start (Docker)

```bash
cp .env.example .env
python scripts/generate_keys.py     # paste the generated secrets into .env
# Fill WHATSAPP_* from your Meta App (Cloud API) setup.
docker compose up --build           # add: --profile local-ai  for Ollama
```

- API:        http://localhost/health
- Dashboard:  http://localhost/
- API docs:   http://localhost/docs  (non-production)

## Local development (backend)

```bash
cd backend
pip install -e ".[dev]"
python -m pytest -m "not performance"               # run tests
alembic upgrade head                                 # apply migrations (needs Postgres)
uvicorn app.main:app --reload                        # run the API
celery -A app.workers.celery_app.celery_app worker --loglevel=info
celery -A app.workers.celery_app.celery_app beat   --loglevel=info
```

Optional extras: `pip install -e ".[dev,ai,documents]"` to add vendor SDKs /
LangGraph and the PDF/OCR pipeline.

## Documentation

| Guide | File |
|---|---|
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Project structure | [docs/STRUCTURE.md](docs/STRUCTURE.md) |
| Environment variables | [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) |
| Database | [docs/DATABASE.md](docs/DATABASE.md) |
| Testing | [docs/TESTING.md](docs/TESTING.md) |
| Deployment | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| Security | [docs/SECURITY.md](docs/SECURITY.md) |
| Troubleshooting | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |

## Privacy

Messages belong only to you: no telemetry, no analytics, no data selling.
Run entirely locally with Ollama, delete all stored data, or export everything.

## WhatsApp integration & compliance

This project uses the **official WhatsApp Cloud API** for a business number you
own. It does **not** automate a personal consumer WhatsApp account through
unofficial methods, which would violate WhatsApp's Terms of Service. The
messaging channel sits behind a `MessagingProvider` interface so it can be
swapped for another official provider.

## License

MIT

---

_This repository began as a Python-learning space (VS Code, Git workflow, first
programs). The assistant above is built on top of that history._

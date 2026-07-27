# Project Structure

```
.
├── backend/                     # FastAPI application + Celery workers
│   ├── app/
│   │   ├── api/                 # HTTP layer (thin — no business logic)
│   │   │   ├── routers/         # Endpoint groups: auth, webhook, conversations,
│   │   │   │                    #   memory, tasks, notes, reminders, files,
│   │   │   │                    #   documents, settings, prompts, health, analytics
│   │   │   └── deps/            # FastAPI dependencies (auth, db session, rate limit)
│   │   ├── services/            # Application/use-case layer (business logic)
│   │   ├── agents/              # Agent orchestration
│   │   │   ├── graph/           # LangGraph state machine (nodes, edges, state)
│   │   │   └── tools/           # Tools: reminders, tasks, notes, web, weather,
│   │   │                        #   news, translate, rag_qa, email, expenses, etc.
│   │   ├── llm/                 # LLM abstraction
│   │   │   └── providers/       # openai, gemini, claude, ollama adapters + router
│   │   ├── memory/              # Short/long-term memory services
│   │   ├── rag/                 # Chunking, embedding, retrieval, re-ranking
│   │   ├── messaging/           # Messaging channel abstraction
│   │   │   └── providers/       # cloud_api (default) + future adapters
│   │   ├── database/            # DB engine/session + repositories
│   │   │   └── repositories/    # Repository pattern per aggregate
│   │   ├── models/             # SQLAlchemy ORM models (domain persistence)
│   │   ├── schemas/            # Pydantic request/response DTOs
│   │   ├── middleware/         # Security, logging, rate-limit, request-id middleware
│   │   ├── security/           # Crypto (AES-256-GCM), JWT, hashing, injection guards
│   │   ├── core/              # App bootstrap, exceptions, DI container, logging setup
│   │   ├── config/           # Pydantic Settings (typed env configuration)
│   │   ├── utils/            # Reusable helpers (dates, redaction, retries)
│   │   ├── workers/         # Celery app + tasks (OCR, STT, embeddings, digests)
│   │   └── commands/        # WhatsApp slash-command handlers (/help, /search, …)
│   ├── tests/               # unit / integration / security / api / performance
│   └── alembic/             # DB migrations
├── frontend/                # Next.js + Tailwind admin dashboard
│   └── src/{app,components,lib,hooks}
├── docker/                  # nginx + postgres init assets
├── scripts/                 # Dev/ops scripts (seed, backup, key-rotation)
├── docs/                    # Architecture, guides, API docs
└── .github/workflows/       # CI/CD pipelines
```

## Dependency direction

```
api  →  services  →  {repositories, agents, memory, rag, messaging, llm}
services  →  domain models/schemas
infrastructure adapters implement the ports defined near the services
```

The API layer never contains business logic; services never import FastAPI;
domain models never import SQL/HTTP frameworks. This keeps every layer
independently testable and every provider swappable.

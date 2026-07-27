"""Typed application configuration.

All runtime configuration is defined here as nested Pydantic ``BaseSettings``
models. Values are read from environment variables (and an optional ``.env``
file in development). Nothing in the codebase should read ``os.environ``
directly — always depend on :func:`get_settings` so configuration is validated,
typed, cached, and easy to override in tests.

Design notes
------------
* **Nested config** — each concern (database, redis, security, whatsapp, each
  LLM provider, celery, rag) is its own model with an ``env_prefix`` so related
  variables group together (e.g. ``DB_HOST``, ``DB_PORT``).
* **Secrets are ``SecretStr``** — they never render in logs, tracebacks, or
  ``repr`` output. Call ``.get_secret_value()`` only at the point of use.
* **Fail fast** — invalid or missing required configuration raises at startup,
  not at first request.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import (
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Environment(str, Enum):
    """Deployment environment."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LLMProviderName(str, Enum):
    """Supported LLM providers. ``ollama`` enables fully local operation."""

    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"
    OLLAMA = "ollama"


class VectorStoreName(str, Enum):
    PGVECTOR = "pgvector"
    CHROMA = "chroma"


# ---------------------------------------------------------------------------
# Base for every nested settings model
# ---------------------------------------------------------------------------


class _Base(BaseSettings):
    """Shared config: read from env + optional .env, ignore unknown vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class AppSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="APP_")

    name: str = "WhatsApp AI Assistant"
    environment: Environment = Environment.LOCAL
    debug: bool = False
    log_level: LogLevel = LogLevel.INFO
    # Bind all interfaces inside the container (intentional).
    host: str = "0.0.0.0"  # noqa: S104  # nosec B104
    port: int = 8000
    # Public base URL used to build webhook/callback URLs.
    base_url: str = "http://localhost:8000"
    # Comma-separated list of allowed CORS origins for the dashboard.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


class DatabaseSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    user: str = "assistant"
    password: SecretStr = SecretStr("assistant")
    name: str = "assistant"
    # Connection pool tuning.
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True
    echo: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dsn(self) -> str:
        """Async SQLAlchemy DSN (asyncpg driver)."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.user,
                password=self.password.get_secret_value(),
                host=self.host,
                port=self.port,
                path=self.name,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_dsn(self) -> str:
        """Sync DSN (psycopg) for Alembic migrations."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.user,
                password=self.password.get_secret_value(),
                host=self.host,
                port=self.port,
                path=self.name,
            )
        )


# ---------------------------------------------------------------------------
# Redis (cache / broker / rate-limit / replay guard)
# ---------------------------------------------------------------------------


class RedisSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dsn(self) -> str:
        auth = f":{self.password.get_secret_value()}@" if self.password else ""
        return str(
            RedisDsn.build(
                scheme="redis", host=f"{auth}{self.host}", port=self.port, path=str(self.db)
            )
        )


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


class SecuritySettings(_Base):
    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    # JWT
    jwt_secret: SecretStr = SecretStr("change-me-in-production")
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14

    # AES-256-GCM data-encryption key. MUST be a base64-encoded 32-byte key in
    # production (generate: ``python scripts/generate_keys.py``).
    encryption_key: SecretStr = SecretStr("")

    # Rate limiting (per client, sliding window).
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Webhook replay protection window (seconds).
    webhook_replay_window_seconds: int = 300

    @field_validator("jwt_secret", "encryption_key")
    @classmethod
    def _not_default_in_prod(cls, value: SecretStr) -> SecretStr:
        # Hard failure for placeholder secrets is enforced in Settings.validate_runtime()
        # where we also know the environment; here we only strip accidental whitespace.
        raw = value.get_secret_value()
        return SecretStr(raw.strip())


# ---------------------------------------------------------------------------
# WhatsApp (official Cloud API)
# ---------------------------------------------------------------------------


class WhatsAppSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="WHATSAPP_")

    # Meta Graph API version and identifiers.
    api_version: str = "v20.0"
    phone_number_id: str = ""
    business_account_id: str = ""
    access_token: SecretStr = SecretStr("")
    # Token used to verify the webhook subscription handshake.
    verify_token: SecretStr = SecretStr("")
    # App secret used to validate the X-Hub-Signature-256 HMAC on every event.
    app_secret: SecretStr = SecretStr("")
    # Only messages from this owner number are accepted (privacy: your number only).
    owner_phone_number: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def graph_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"


# ---------------------------------------------------------------------------
# LLM providers + router policy
# ---------------------------------------------------------------------------


class OpenAISettings(_Base):
    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    api_key: SecretStr | None = None
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    base_url: str | None = None


class GeminiSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="GEMINI_")

    api_key: SecretStr | None = None
    chat_model: str = "gemini-1.5-flash"
    embedding_model: str = "text-embedding-004"


class ClaudeSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="CLAUDE_")

    api_key: SecretStr | None = None
    chat_model: str = "claude-3-5-sonnet-latest"


class OllamaSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="OLLAMA_")

    base_url: str = "http://localhost:11434"
    chat_model: str = "llama3.1"
    embedding_model: str = "nomic-embed-text"


class LLMSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="LLM_")

    # Default provider and ordered fallback chain used by the LLM router.
    default_provider: LLMProviderName = LLMProviderName.OPENAI
    fallback_providers: Annotated[list[LLMProviderName], NoDecode] = Field(default_factory=list)
    request_timeout_seconds: int = 60
    max_retries: int = 2
    temperature: float = 0.3
    # Vector dimensionality must match the embedding model used.
    embedding_dimensions: int = 1536

    @field_validator("fallback_providers", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [p.strip() for p in value.split(",") if p.strip()]
        return value


# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------


class CelerySettings(_Base):
    model_config = SettingsConfigDict(env_prefix="CELERY_")

    broker_db: int = 1
    result_db: int = 2
    task_time_limit_seconds: int = 600
    task_soft_time_limit_seconds: int = 540


# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------


class RAGSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="RAG_")

    vector_store: VectorStoreName = VectorStoreName.PGVECTOR
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 6
    # Number of recent conversation turns kept in working memory (Redis).
    working_memory_turns: int = 12


# ---------------------------------------------------------------------------
# Root settings aggregate
# ---------------------------------------------------------------------------


class Settings(_Base):
    """Root configuration object composing every nested settings group."""

    app: AppSettings = Field(default_factory=AppSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    whatsapp: WhatsAppSettings = Field(default_factory=WhatsAppSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    claude: ClaudeSettings = Field(default_factory=ClaudeSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)

    def validate_runtime(self) -> None:
        """Enforce production-grade invariants. Call once at startup.

        Raises
        ------
        ValueError
            If placeholder secrets are used in a non-local environment.
        """
        if self.app.environment == Environment.LOCAL:
            return

        problems: list[str] = []
        if self.security.jwt_secret.get_secret_value() in {"", "change-me-in-production"}:
            problems.append("SECURITY_JWT_SECRET must be set to a strong random value")
        if not self.security.encryption_key.get_secret_value():
            problems.append("SECURITY_ENCRYPTION_KEY must be set (base64 32-byte key)")
        if not self.whatsapp.app_secret.get_secret_value():
            problems.append("WHATSAPP_APP_SECRET must be set for webhook verification")
        if not self.whatsapp.verify_token.get_secret_value():
            problems.append("WHATSAPP_VERIFY_TOKEN must be set")
        if problems:
            raise ValueError(
                "Insecure configuration for environment "
                f"'{self.app.environment.value}':\n  - " + "\n  - ".join(problems)
            )


@lru_cache
def get_settings() -> Settings:
    """Return the cached, validated application settings singleton.

    Cached so environment parsing happens once per process. Tests can override
    by calling ``get_settings.cache_clear()`` after mutating the environment.
    """
    return Settings()

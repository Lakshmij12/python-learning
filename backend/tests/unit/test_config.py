"""Unit tests for the typed configuration layer."""

from __future__ import annotations

import pytest
from app.config.settings import (
    Environment,
    LLMProviderName,
    Settings,
    VectorStoreName,
    get_settings,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Ensure each test parses the environment fresh."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults_load() -> None:
    s = get_settings()
    assert s.app.environment == Environment.LOCAL
    assert s.llm.default_provider == LLMProviderName.OPENAI
    assert s.rag.vector_store == VectorStoreName.PGVECTOR


def test_dsn_is_async_and_masks_password() -> None:
    s = get_settings()
    assert s.db.dsn.startswith("postgresql+asyncpg://")
    assert s.db.sync_dsn.startswith("postgresql+psycopg://")


def test_secrets_are_masked_in_repr() -> None:
    s = get_settings()
    assert "change-me" not in repr(s.security.jwt_secret)
    assert "**" in repr(s.security.jwt_secret)


def test_cors_origins_split_from_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", "http://a.com, http://b.com")
    get_settings.cache_clear()
    s = get_settings()
    assert s.app.cors_origins == ["http://a.com", "http://b.com"]


def test_local_env_skips_strict_validation() -> None:
    Settings().validate_runtime()  # no exception in local


def test_production_requires_real_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="Insecure configuration"):
        get_settings().validate_runtime()


def test_fallback_providers_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "ollama, claude")
    get_settings.cache_clear()
    s = get_settings()
    assert s.llm.fallback_providers == [LLMProviderName.OLLAMA, LLMProviderName.CLAUDE]

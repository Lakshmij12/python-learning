"""Unit tests for the LLM router fallback + usage accounting."""

from __future__ import annotations

import pytest

from app.config.settings import LLMProviderName, get_settings
from app.core.exceptions import LLMProviderError
from app.llm.base import ChatMessage, ChatResult, EmbeddingResult, LLMProvider, Role, Usage
from app.llm.router import LLMRouter

pytestmark = pytest.mark.asyncio


class FakeProvider(LLMProvider):
    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self._fail = fail
        self.calls = 0

    async def chat(self, messages, *, model=None, temperature=None, tools=None, max_tokens=None):  # noqa: ANN001
        self.calls += 1
        if self._fail:
            raise LLMProviderError(f"{self.name} down")
        return ChatResult(
            content=f"reply from {self.name}",
            provider=self.name,
            model="fake-model",
            usage=Usage(10, 5),
        )

    async def embed(self, texts, *, model=None):  # noqa: ANN001
        if self._fail:
            raise LLMProviderError(f"{self.name} down")
        return EmbeddingResult(vectors=[[0.1] * 3 for _ in texts], provider=self.name, model="fake")


@pytest.fixture(autouse=True)
def _configure(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "openai")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDERS", "ollama")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_uses_default_provider_first() -> None:
    primary = FakeProvider("openai")
    fallback = FakeProvider("ollama")
    router = LLMRouter(
        providers={LLMProviderName.OPENAI: primary, LLMProviderName.OLLAMA: fallback}
    )
    result = await router.chat([ChatMessage(Role.USER, "hi")])
    assert result.content == "reply from openai"
    assert primary.calls == 1
    assert fallback.calls == 0


async def test_falls_back_when_default_fails() -> None:
    primary = FakeProvider("openai", fail=True)
    fallback = FakeProvider("ollama")
    router = LLMRouter(
        providers={LLMProviderName.OPENAI: primary, LLMProviderName.OLLAMA: fallback}
    )
    result = await router.chat([ChatMessage(Role.USER, "hi")])
    assert result.content == "reply from ollama"
    assert primary.calls == 1
    assert fallback.calls == 1


async def test_raises_when_all_fail() -> None:
    router = LLMRouter(
        providers={
            LLMProviderName.OPENAI: FakeProvider("openai", fail=True),
            LLMProviderName.OLLAMA: FakeProvider("ollama", fail=True),
        }
    )
    with pytest.raises(LLMProviderError, match="All LLM providers failed"):
        await router.chat([ChatMessage(Role.USER, "hi")])


async def test_usage_is_recorded(db_session) -> None:  # noqa: ANN001
    from sqlalchemy import func, select

    from app.models.system import LLMUsage

    router = LLMRouter(
        session=db_session,
        providers={
            LLMProviderName.OPENAI: FakeProvider("openai"),
            LLMProviderName.OLLAMA: FakeProvider("ollama"),
        },
    )
    await router.chat([ChatMessage(Role.USER, "hi")])
    count = (await db_session.execute(select(func.count()).select_from(LLMUsage))).scalar_one()
    assert count == 1

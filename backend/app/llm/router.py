"""LLM router: provider selection, fallback, and usage accounting.

Callers use ``LLMRouter.chat()`` / ``.embed()`` without knowing which backend
serves the request. The router tries the configured default provider first,
then each fallback in order, so a cloud outage transparently degrades to a local
Ollama model. Every call's token usage/cost/latency is optionally recorded.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import LLMProviderName, get_settings
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.llm.base import ChatMessage, ChatResult, EmbeddingResult, LLMProvider, ToolSpec
from app.models.system import LLMUsage

logger = get_logger(__name__)


def _build_provider(name: LLMProviderName) -> LLMProvider:
    if name == LLMProviderName.OPENAI:
        from app.llm.providers.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if name == LLMProviderName.GEMINI:
        from app.llm.providers.gemini_provider import GeminiProvider

        return GeminiProvider()
    if name == LLMProviderName.CLAUDE:
        from app.llm.providers.claude_provider import ClaudeProvider

        return ClaudeProvider()
    if name == LLMProviderName.OLLAMA:
        from app.llm.providers.ollama_provider import OllamaProvider

        return OllamaProvider()
    raise LLMProviderError(f"Unknown provider: {name}")


class LLMRouter:
    """Selects providers with an ordered fallback chain."""

    def __init__(
        self,
        *,
        session: AsyncSession | None = None,
        providers: dict[LLMProviderName, LLMProvider] | None = None,
    ) -> None:
        self._settings = get_settings().llm
        self._session = session
        # Allow injection of fakes in tests; otherwise build lazily.
        self._providers = providers or {}

    def _provider(self, name: LLMProviderName) -> LLMProvider:
        if name not in self._providers:
            self._providers[name] = _build_provider(name)
        return self._providers[name]

    def _chain(self) -> list[LLMProviderName]:
        chain = [self._settings.default_provider, *self._settings.fallback_providers]
        # De-duplicate while preserving order.
        seen: set[LLMProviderName] = set()
        return [p for p in chain if not (p in seen or seen.add(p))]

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[ToolSpec] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        user_id: uuid.UUID | None = None,
    ) -> ChatResult:
        last_error: Exception | None = None
        for name in self._chain():
            try:
                provider = self._provider(name)
                result = await provider.chat(
                    messages, temperature=temperature, tools=tools, max_tokens=max_tokens
                )
                await self._record(result, "chat", user_id, success=True)
                return result
            except Exception as exc:  # noqa: BLE001 - try the next provider
                last_error = exc
                logger.warning("llm.provider_failed", provider=name.value, error=str(exc))
                continue
        raise LLMProviderError("All LLM providers failed.") from last_error

    async def embed(self, texts: list[str], *, user_id: uuid.UUID | None = None) -> EmbeddingResult:
        last_error: Exception | None = None
        for name in self._chain():
            try:
                result = await self._provider(name).embed(texts)
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning("llm.embed_failed", provider=name.value, error=str(exc))
                continue
        raise LLMProviderError("All embedding providers failed.") from last_error

    async def _record(
        self, result: ChatResult, operation: str, user_id: uuid.UUID | None, *, success: bool
    ) -> None:
        if self._session is None:
            return
        self._session.add(
            LLMUsage(
                user_id=user_id,
                provider=result.provider,
                model=result.model,
                operation=operation,
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                total_tokens=result.usage.total_tokens,
                latency_ms=result.latency_ms,
                success=success,
            )
        )
        await self._session.flush()

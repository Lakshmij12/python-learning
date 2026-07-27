"""Anthropic Claude provider adapter (Messages API via httpx)."""

from __future__ import annotations

import time

import httpx

from app.config.settings import get_settings
from app.core.exceptions import ConfigurationError, LLMProviderError
from app.llm.base import (
    ChatMessage,
    ChatResult,
    EmbeddingResult,
    LLMProvider,
    Role,
    ToolSpec,
    Usage,
)

_API = "https://api.anthropic.com/v1/messages"
_VERSION = "2023-06-01"


class ClaudeProvider(LLMProvider):
    name = "claude"
    supports_tools = True

    def __init__(self) -> None:
        self._cfg = get_settings().claude
        self._llm = get_settings().llm

    def _headers(self) -> dict[str, str]:
        if self._cfg.api_key is None:
            raise ConfigurationError("CLAUDE_API_KEY is not configured.")
        return {
            "x-api-key": self._cfg.api_key.get_secret_value(),
            "anthropic-version": _VERSION,
        }

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        # Anthropic takes the system prompt as a top-level field.
        system = "\n\n".join(m.content for m in messages if m.role == Role.SYSTEM)
        convo = [
            {"role": m.role.value, "content": m.content}
            for m in messages
            if m.role in (Role.USER, Role.ASSISTANT)
        ]
        payload: dict = {
            "model": model or self._cfg.chat_model,
            "messages": convo,
            "max_tokens": max_tokens or 1024,
            "temperature": self._llm.temperature if temperature is None else temperature,
        }
        if system:
            payload["system"] = system

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._llm.request_timeout_seconds) as client:
                resp = await client.post(_API, json=payload, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                "Claude request failed.", detail={"status": exc.response.status_code}
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("Claude unreachable.") from exc
        latency = int((time.perf_counter() - started) * 1000)

        text = "".join(block.get("text", "") for block in data.get("content", []))
        usage = data.get("usage", {})
        return ChatResult(
            content=text,
            provider=self.name,
            model=payload["model"],
            usage=Usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
            latency_ms=latency,
        )

    async def embed(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        # Anthropic has no first-party embeddings endpoint; use another provider.
        raise LLMProviderError("Claude does not provide embeddings; use OpenAI/Ollama.")

"""OpenAI (and OpenAI-compatible) provider adapter.

Talks to the REST API directly via httpx so no heavyweight SDK is required and
any OpenAI-compatible endpoint (via ``OPENAI_BASE_URL``) works unchanged.
"""

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
    ToolCall,
    ToolSpec,
    Usage,
)


class OpenAIProvider(LLMProvider):
    name = "openai"
    supports_tools = True

    def __init__(self) -> None:
        self._cfg = get_settings().openai
        self._llm = get_settings().llm

    def _headers(self) -> dict[str, str]:
        if self._cfg.api_key is None:
            raise ConfigurationError("OPENAI_API_KEY is not configured.")
        return {"Authorization": f"Bearer {self._cfg.api_key.get_secret_value()}"}

    def _base_url(self) -> str:
        return (self._cfg.base_url or "https://api.openai.com/v1").rstrip("/")

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        payload: dict = {
            "model": model or self._cfg.chat_model,
            "messages": [
                {"role": m.role.value, "content": m.content, **({"name": m.name} if m.name else {})}
                for m in messages
            ],
            "temperature": self._llm.temperature if temperature is None else temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ]

        started = time.perf_counter()
        data = await self._post("/chat/completions", payload)
        latency = int((time.perf_counter() - started) * 1000)

        choice = data["choices"][0]["message"]
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["function"]["name"], arguments=_safe_json(tc["function"]["arguments"]))
            for tc in choice.get("tool_calls", []) or []
        ]
        usage = data.get("usage", {})
        return ChatResult(
            content=choice.get("content") or "",
            provider=self.name,
            model=payload["model"],
            usage=Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
            tool_calls=tool_calls,
            latency_ms=latency,
        )

    async def embed(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        payload = {"model": model or self._cfg.embedding_model, "input": texts}
        data = await self._post("/embeddings", payload)
        vectors = [item["embedding"] for item in data["data"]]
        usage = data.get("usage", {})
        return EmbeddingResult(
            vectors=vectors,
            provider=self.name,
            model=payload["model"],
            usage=Usage(usage.get("prompt_tokens", 0), 0),
        )

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self._base_url()}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._llm.request_timeout_seconds) as client:
                resp = await client.post(url, json=payload, headers=self._headers())
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                "OpenAI request failed.", detail={"status": exc.response.status_code}
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("OpenAI unreachable.") from exc


def _safe_json(raw: str) -> dict:
    import json

    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}

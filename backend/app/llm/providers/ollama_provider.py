"""Ollama provider adapter — fully local, private inference (no cloud calls)."""

from __future__ import annotations

import time

import httpx

from app.config.settings import get_settings
from app.core.exceptions import LLMProviderError
from app.llm.base import (
    ChatMessage,
    ChatResult,
    EmbeddingResult,
    LLMProvider,
    ToolSpec,
    Usage,
)


class OllamaProvider(LLMProvider):
    name = "ollama"
    supports_tools = False  # depends on model; kept conservative

    def __init__(self) -> None:
        self._cfg = get_settings().ollama
        self._llm = get_settings().llm

    def _base_url(self) -> str:
        return self._cfg.base_url.rstrip("/")

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        payload = {
            "model": model or self._cfg.chat_model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": self._llm.temperature if temperature is None else temperature
            },
        }
        started = time.perf_counter()
        data = await self._post("/api/chat", payload)
        latency = int((time.perf_counter() - started) * 1000)
        return ChatResult(
            content=data.get("message", {}).get("content", ""),
            provider=self.name,
            model=payload["model"],
            usage=Usage(
                data.get("prompt_eval_count", 0) or 0, data.get("eval_count", 0) or 0
            ),
            latency_ms=latency,
        )

    async def embed(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        vectors: list[list[float]] = []
        for text in texts:
            data = await self._post(
                "/api/embeddings", {"model": model or self._cfg.embedding_model, "prompt": text}
            )
            vectors.append(data.get("embedding", []))
        return EmbeddingResult(vectors=vectors, provider=self.name, model=model or self._cfg.embedding_model)

    async def _post(self, path: str, payload: dict) -> dict:
        url = f"{self._base_url()}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._llm.request_timeout_seconds) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as exc:
            raise LLMProviderError("Ollama unreachable.") from exc

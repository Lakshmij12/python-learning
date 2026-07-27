"""Google Gemini provider adapter (Generative Language API via httpx)."""

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

_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    name = "gemini"
    supports_tools = True

    def __init__(self) -> None:
        self._cfg = get_settings().gemini
        self._llm = get_settings().llm

    def _key(self) -> str:
        if self._cfg.api_key is None:
            raise ConfigurationError("GEMINI_API_KEY is not configured.")
        return self._cfg.api_key.get_secret_value()

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        model_name = model or self._cfg.chat_model
        contents = []
        system_instruction = None
        for m in messages:
            if m.role == Role.SYSTEM:
                system_instruction = {"parts": [{"text": m.content}]}
                continue
            role = "model" if m.role == Role.ASSISTANT else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": self._llm.temperature if temperature is None else temperature
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens

        url = f"{_BASE}/models/{model_name}:generateContent?key={self._key()}"
        started = time.perf_counter()
        data = await self._post(url, payload)
        latency = int((time.perf_counter() - started) * 1000)

        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        meta = data.get("usageMetadata", {})
        return ChatResult(
            content=text,
            provider=self.name,
            model=model_name,
            usage=Usage(meta.get("promptTokenCount", 0), meta.get("candidatesTokenCount", 0)),
            latency_ms=latency,
        )

    async def embed(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        model_name = model or self._cfg.embedding_model
        vectors: list[list[float]] = []
        for text in texts:
            url = f"{_BASE}/models/{model_name}:embedContent?key={self._key()}"
            payload = {"content": {"parts": [{"text": text}]}}
            data = await self._post(url, payload)
            vectors.append(data.get("embedding", {}).get("values", []))
        return EmbeddingResult(vectors=vectors, provider=self.name, model=model_name)

    async def _post(self, url: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._llm.request_timeout_seconds) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                "Gemini request failed.", detail={"status": exc.response.status_code}
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("Gemini unreachable.") from exc

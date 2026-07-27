"""LLM provider port (interface) and shared value objects.

Every AI backend (OpenAI, Gemini, Claude, Ollama) implements ``LLMProvider``.
The rest of the system depends only on this interface via the ``LLMRouter``, so
providers — including a fully-local Ollama — are interchangeable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(slots=True)
class ChatMessage:
    role: Role
    content: str
    name: str | None = None


@dataclass(slots=True)
class ToolSpec:
    """A tool/function the model may call (function-calling)."""

    name: str
    description: str
    parameters: dict  # JSON schema


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(slots=True)
class ChatResult:
    content: str
    provider: str
    model: str
    usage: Usage = field(default_factory=Usage)
    tool_calls: list[ToolCall] = field(default_factory=list)
    latency_ms: int = 0


@dataclass(slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    provider: str
    model: str
    usage: Usage = field(default_factory=Usage)


class LLMProvider(ABC):
    """Abstract chat + embedding backend."""

    name: str = "base"
    supports_tools: bool = False

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Generate a chat completion."""

    @abstractmethod
    async def embed(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        """Embed one or more texts."""

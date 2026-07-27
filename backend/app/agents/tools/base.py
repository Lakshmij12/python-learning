"""Agent tool interface and registry.

Tools are the actions the agent can take (create a task, add a reminder, search
documents, …). Each declares a JSON-schema so it can be exposed to the LLM via
function-calling and, later, over MCP. Tools receive a ``ToolContext`` carrying
the DB session, the acting user, and the LLM router.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import ToolSpec
from app.llm.router import LLMRouter


@dataclass(slots=True)
class ToolContext:
    session: AsyncSession
    user_id: uuid.UUID
    router: LLMRouter


class Tool(ABC):
    name: str = "tool"
    description: str = ""
    parameters: dict = {"type": "object", "properties": {}}

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, parameters=self.parameters)

    @abstractmethod
    async def run(self, args: dict, ctx: ToolContext) -> str:
        """Execute the tool and return a short human-readable result string."""


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

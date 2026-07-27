"""Agent orchestrator.

Implements the reasoning loop as an explicit state machine (mirroring a LangGraph
graph: ``guard -> retrieve -> build_context -> generate -> act -> respond``).
Keeping the nodes as plain async methods makes the flow debuggable and unit
-testable with a fake LLM router, while remaining a drop-in for LangGraph.

Security: inbound text and any retrieved/stored content are treated as
untrusted. Obvious prompt-injection attempts are refused; retrieved content is
sanitised before entering the prompt.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.base import ToolContext, ToolRegistry
from app.agents.tools.productivity import default_tools
from app.core.logging import get_logger
from app.llm.base import ChatMessage, Role
from app.llm.router import LLMRouter
from app.memory.context import ContextBuilder
from app.memory.working import WorkingMemory
from app.rag.retriever import Retriever
from app.security.injection import scan

logger = get_logger(__name__)

_REFUSAL = (
    "I can't act on that request because it looks like it's trying to change my "
    "instructions. Let me know how I can help with your tasks, notes, or questions."
)


@dataclass(slots=True)
class AgentState:
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    user_input: str
    prompt: list[ChatMessage] = field(default_factory=list)
    rag_context: str = ""
    response: str = ""


class AgentService:
    def __init__(
        self,
        session: AsyncSession,
        router: LLMRouter,
        *,
        redis: object | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.session = session
        self.router = router
        self.working = WorkingMemory(redis)
        self.context_builder = ContextBuilder(session, router, self.working)
        self.retriever = Retriever(session, router)
        self.registry = registry or ToolRegistry(default_tools())

    async def handle(
        self, *, user_id: uuid.UUID, conversation_id: uuid.UUID, text: str
    ) -> str:
        state = AgentState(user_id=user_id, conversation_id=conversation_id, user_input=text)

        # 1. Guard against prompt injection.
        if scan(text).is_suspicious:
            logger.warning("agent.injection_refused", conversation_id=str(conversation_id))
            state.response = _REFUSAL
            return await self._finish(state)

        # 2. Retrieve grounding context (RAG).
        retrieval = await self.retriever.retrieve(query=text, user_id=user_id)
        state.rag_context = retrieval.context

        # 3. Build the prompt from memory tiers.
        state.prompt = await self.context_builder.build(
            user_id=user_id, conversation_id=conversation_id, user_input=text
        )
        if state.rag_context:
            state.prompt.insert(
                1, ChatMessage(Role.SYSTEM, f"Relevant document context:\n{state.rag_context}")
            )

        # 4. Generate, optionally calling a tool once.
        result = await self.router.chat(
            state.prompt, tools=self.registry.specs(), user_id=user_id
        )
        if result.tool_calls:
            tool_output = await self._run_tools(result.tool_calls, user_id)
            # 5. Second pass: let the model turn tool output into a reply.
            follow_up = [
                *state.prompt,
                ChatMessage(Role.ASSISTANT, result.content or ""),
                ChatMessage(Role.TOOL, tool_output),
                ChatMessage(
                    Role.SYSTEM,
                    "Summarise the tool result above for the user in one short message.",
                ),
            ]
            final = await self.router.chat(follow_up, user_id=user_id)
            state.response = final.content or tool_output
        else:
            state.response = result.content

        return await self._finish(state)

    async def _run_tools(self, tool_calls, user_id: uuid.UUID) -> str:  # noqa: ANN001
        ctx = ToolContext(session=self.session, user_id=user_id, router=self.router)
        outputs: list[str] = []
        for call in tool_calls:
            tool = self.registry.get(call.name)
            if tool is None:
                outputs.append(f"(unknown tool: {call.name})")
                continue
            try:
                outputs.append(await tool.run(call.arguments, ctx))
            except Exception as exc:  # noqa: BLE001
                logger.error("agent.tool_failed", tool=call.name, error=str(exc))
                outputs.append(f"(the {call.name} action failed)")
        return "\n".join(outputs)

    async def _finish(self, state: AgentState) -> str:
        # Update working memory with this turn.
        await self.working.append(state.conversation_id, Role.USER, state.user_input)
        if state.response:
            await self.working.append(state.conversation_id, Role.ASSISTANT, state.response)
        return state.response

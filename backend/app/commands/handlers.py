"""Slash-command handlers.

Commands offer deterministic, no-LLM shortcuts (``/task``, ``/note``, ``/remind``,
``/help``, ``/status`` …). Anything not recognised as a command is routed to the
agent instead.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.repositories import (
    NoteRepository,
    ReminderRepository,
    TaskRepository,
)
from app.security.crypto import encrypt

Handler = Callable[["CommandContext"], Awaitable[str]]


@dataclass(slots=True)
class CommandContext:
    session: AsyncSession
    user_id: uuid.UUID
    args: str


_HELP = (
    "🤖 *Assistant commands*\n"
    "/help – show this help\n"
    "/task <title> – create a task\n"
    "/note <text> – save a note\n"
    "/remind <ISO-time> | <message> – set a reminder\n"
    "/tasks – list open tasks\n"
    "/status – service status\n"
    "Anything else is answered by the AI assistant."
)


async def cmd_help(_: CommandContext) -> str:
    return _HELP


async def cmd_task(ctx: CommandContext) -> str:
    title = ctx.args.strip()
    if not title:
        return "Usage: /task <title>"
    await TaskRepository(ctx.session).create(user_id=ctx.user_id, title=title)
    return f"✅ Task created: “{title}”."


async def cmd_note(ctx: CommandContext) -> str:
    text = ctx.args.strip()
    if not text:
        return "Usage: /note <text>"
    await NoteRepository(ctx.session).create(user_id=ctx.user_id, content=encrypt(text))
    return "📝 Note saved."


async def cmd_remind(ctx: CommandContext) -> str:
    # Format: /remind 2026-01-01T09:00:00Z | Call the dentist
    if "|" not in ctx.args:
        return "Usage: /remind <ISO-8601 time> | <message>"
    raw_time, _, message = ctx.args.partition("|")
    message = message.strip()
    try:
        remind_at = datetime.fromisoformat(raw_time.strip().replace("Z", "+00:00"))
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=UTC)
    except ValueError:
        return "Couldn't parse the time. Example: /remind 2026-01-01T09:00:00Z | Call the dentist"
    if not message:
        return "Please include a reminder message after '|'."
    await ReminderRepository(ctx.session).create(
        user_id=ctx.user_id, message=message, remind_at=remind_at
    )
    return f"⏰ Reminder set for {remind_at.isoformat()}."


async def cmd_tasks(ctx: CommandContext) -> str:
    tasks = await TaskRepository(ctx.session).list(user_id=ctx.user_id, limit=20)
    open_tasks = [t for t in tasks if t.status.value in {"todo", "in_progress"}]
    if not open_tasks:
        return "You have no open tasks. 🎉"
    return "Your open tasks:\n" + "\n".join(f"• {t.title} ({t.priority.value})" for t in open_tasks)


async def cmd_status(_: CommandContext) -> str:
    return "🟢 Assistant is online."


_COMMANDS: dict[str, Handler] = {
    "help": cmd_help,
    "task": cmd_task,
    "note": cmd_note,
    "remind": cmd_remind,
    "tasks": cmd_tasks,
    "status": cmd_status,
}


class CommandRouter:
    """Parses and dispatches ``/command args`` strings."""

    @staticmethod
    def is_command(text: str) -> bool:
        return text.lstrip().startswith("/")

    @staticmethod
    async def handle(text: str, *, session: AsyncSession, user_id: uuid.UUID) -> str:
        stripped = text.lstrip()[1:]  # drop leading '/'
        name, _, args = stripped.partition(" ")
        handler = _COMMANDS.get(name.lower())
        if handler is None:
            return f"Unknown command '/{name}'. Send /help for the list."
        ctx = CommandContext(session=session, user_id=user_id, args=args)
        return await handler(ctx)

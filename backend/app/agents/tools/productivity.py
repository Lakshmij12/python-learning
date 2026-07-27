"""Concrete DB-backed agent tools: tasks, notes, reminders."""

from __future__ import annotations

from datetime import datetime, timezone

from app.agents.tools.base import Tool, ToolContext
from app.database.repositories.repositories import (
    NoteRepository,
    ReminderRepository,
    TaskRepository,
)
from app.models.enums import Priority
from app.security.crypto import encrypt


class CreateTaskTool(Tool):
    name = "create_task"
    description = "Create a to-do task for the owner."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Task title"},
            "priority": {
                "type": "string",
                "enum": [p.value for p in Priority],
                "description": "Task priority",
            },
        },
        "required": ["title"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> str:
        title = (args.get("title") or "").strip()
        if not title:
            return "I need a task title to create a task."
        priority = Priority(args["priority"]) if args.get("priority") in {p.value for p in Priority} else Priority.MEDIUM
        task = await TaskRepository(ctx.session).create(
            user_id=ctx.user_id, title=title, priority=priority
        )
        return f"✅ Task created: “{title}” (priority: {priority.value}, id {str(task.id)[:8]})."


class CreateNoteTool(Tool):
    name = "create_note"
    description = "Save a note for the owner."
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Note body"},
            "title": {"type": "string", "description": "Optional note title"},
        },
        "required": ["content"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> str:
        content = (args.get("content") or "").strip()
        if not content:
            return "I need some text to save a note."
        await NoteRepository(ctx.session).create(
            user_id=ctx.user_id,
            title=(args.get("title") or None),
            content=encrypt(content),
        )
        return "📝 Note saved."


class CreateReminderTool(Tool):
    name = "create_reminder"
    description = "Schedule a reminder at a specific ISO-8601 UTC time."
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "What to be reminded about"},
            "remind_at": {
                "type": "string",
                "description": "ISO-8601 UTC datetime, e.g. 2026-01-01T09:00:00Z",
            },
        },
        "required": ["message", "remind_at"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> str:
        message = (args.get("message") or "").strip()
        raw_time = (args.get("remind_at") or "").strip()
        if not message or not raw_time:
            return "I need both a message and a time to set a reminder."
        try:
            remind_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            if remind_at.tzinfo is None:
                remind_at = remind_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return "I couldn't parse that time. Use ISO-8601, e.g. 2026-01-01T09:00:00Z."
        await ReminderRepository(ctx.session).create(
            user_id=ctx.user_id, message=message, remind_at=remind_at
        )
        return f"⏰ Reminder set for {remind_at.isoformat()}."


class ListTasksTool(Tool):
    name = "list_tasks"
    description = "List the owner's open tasks."
    parameters = {"type": "object", "properties": {}}

    async def run(self, args: dict, ctx: ToolContext) -> str:
        tasks = await TaskRepository(ctx.session).list(user_id=ctx.user_id, limit=10)
        open_tasks = [t for t in tasks if t.status.value in {"todo", "in_progress"}]
        if not open_tasks:
            return "You have no open tasks. 🎉"
        lines = [f"• {t.title} ({t.priority.value})" for t in open_tasks]
        return "Your open tasks:\n" + "\n".join(lines)


def default_tools() -> list[Tool]:
    return [CreateTaskTool(), CreateNoteTool(), CreateReminderTool(), ListTasksTool()]

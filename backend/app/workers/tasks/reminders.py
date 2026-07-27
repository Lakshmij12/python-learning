"""Celery task: dispatch due reminders over WhatsApp.

Runs every minute (Celery Beat). Bridges the sync Celery worker to the async
data/messaging layer with ``asyncio.run``.
"""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.database.session import session_scope
from app.messaging.factory import get_messaging_provider
from app.models.enums import ReminderStatus
from app.utils.time import utcnow
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.reminders.dispatch_due_reminders")
def dispatch_due_reminders() -> int:
    """Send all reminders whose time has arrived. Returns the count sent."""
    return asyncio.run(_dispatch())


async def _dispatch() -> int:
    from app.database.repositories.repositories import (
        ReminderRepository,
        UserRepository,
    )

    provider = get_messaging_provider()
    sent = 0
    async with session_scope() as session:
        reminders = await ReminderRepository(session).due(utcnow())
        owner = await UserRepository(session).first_active()
        to_number = owner.whatsapp_number if owner else None
        repo = ReminderRepository(session)
        for reminder in reminders:
            if to_number:
                try:
                    await provider.send_text(to=to_number, text=f"⏰ Reminder: {reminder.message}")
                    sent += 1
                except Exception as exc:  # noqa: BLE001
                    logger.error("reminder.send_failed", id=str(reminder.id), error=str(exc))
                    continue
            await repo.update(reminder, status=ReminderStatus.SENT, sent_at=utcnow())
    if sent:
        logger.info("reminders.dispatched", count=sent)
    return sent

"""Celery application and beat schedule.

Long-running or scheduled work (reminder dispatch, document indexing, daily/
weekly digests, transcription/OCR) runs off the request path in Celery workers.
Broker and result backend use dedicated Redis logical databases.
"""

from __future__ import annotations

from celery import Celery

from app.config.settings import get_settings


def _redis_url(db: int) -> str:
    r = get_settings().redis
    auth = f":{r.password.get_secret_value()}@" if r.password else ""
    return f"redis://{auth}{r.host}:{r.port}/{db}"


def create_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "assistant",
        broker=_redis_url(settings.celery.broker_db),
        backend=_redis_url(settings.celery.result_db),
        include=["app.workers.tasks.reminders"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_time_limit=settings.celery.task_time_limit_seconds,
        task_soft_time_limit=settings.celery.task_soft_time_limit_seconds,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        beat_schedule={
            "dispatch-due-reminders": {
                "task": "app.workers.tasks.reminders.dispatch_due_reminders",
                "schedule": 60.0,  # every minute
            },
        },
    )
    return app


celery_app = create_celery()

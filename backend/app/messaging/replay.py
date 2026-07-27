"""Webhook replay protection.

Two defences against replayed/duplicate webhook deliveries:
* **Freshness** — reject events whose timestamp is older than the configured
  replay window.
* **Idempotency** — a Redis ``SET NX`` on the provider message id ensures each
  message is processed at most once within the window.

The guard degrades safely: if Redis is unavailable it falls back to the
database-level unique constraint on ``messages.provider_message_id`` (the
freshness check still applies).
"""

from __future__ import annotations

import time

from app.config.settings import get_settings
from app.core.exceptions import WebhookVerificationError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ReplayGuard:
    """Detects stale or duplicate webhook events."""

    def __init__(self, redis: object | None) -> None:
        self._redis = redis
        self._window = get_settings().security.webhook_replay_window_seconds

    def check_fresh(self, timestamp: int) -> None:
        """Raise if the event timestamp is outside the replay window."""
        if timestamp <= 0:
            return  # provider omitted a timestamp; rely on idempotency only
        age = int(time.time()) - timestamp
        if age > self._window:
            raise WebhookVerificationError("Webhook event is too old (possible replay).")

    async def is_duplicate(self, message_id: str) -> bool:
        """Return True if this message id was already seen (best-effort)."""
        if not message_id or self._redis is None:
            return False
        try:
            # SET key value NX EX window -> None if key already existed.
            was_set = await self._redis.set(  # type: ignore[attr-defined]
                f"wh:seen:{message_id}", "1", nx=True, ex=self._window
            )
            return not bool(was_set)
        except Exception:  # noqa: BLE001 - never let cache failure drop a message
            logger.warning("replay_guard.redis_unavailable", message_id=message_id)
            return False

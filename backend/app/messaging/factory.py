"""Messaging provider factory.

Central place to select the active messaging channel. Today only the official
WhatsApp Cloud API is wired; additional official providers can be registered
here without touching call sites.
"""

from __future__ import annotations

from functools import lru_cache

from app.messaging.base import MessagingProvider
from app.messaging.providers.cloud_api import CloudApiProvider


@lru_cache
def get_messaging_provider() -> MessagingProvider:
    """Return the process-wide messaging provider singleton."""
    return CloudApiProvider()

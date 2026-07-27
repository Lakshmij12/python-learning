"""Datetime helpers.

Centralises timezone-aware "now" and a coercion helper. Some database drivers
(notably SQLite) return naive datetimes even for ``timezone=True`` columns;
``ensure_aware`` normalises those to UTC so comparisons never raise
``TypeError: can't compare offset-naive and offset-aware datetimes``.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime | None) -> datetime | None:
    """Return ``value`` as timezone-aware UTC (assume UTC if naive)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value

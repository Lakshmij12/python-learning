"""Structured, secret-safe logging setup (structlog).

Goals
-----
* **Never log secrets.** A redaction processor scrubs values whose keys look
  sensitive (token, secret, password, api_key, authorization, …) and masks
  anything matching common secret patterns in free-text event messages.
* **Structured output.** JSON in non-local environments (machine-parseable),
  colourised key-value output locally (human-friendly).
* **Correlation.** A ``request_id`` is bound per request by middleware and
  automatically included on every log line within that request.

Call :func:`configure_logging` once at startup, then obtain loggers via
``structlog.get_logger(__name__)`` anywhere.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

from app.config.settings import Environment, get_settings

# Keys whose values must always be masked, regardless of type.
_SENSITIVE_KEYS = re.compile(
    r"(pass(word)?|secret|token|api[_-]?key|authorization|cookie|credential|private[_-]?key)",
    re.IGNORECASE,
)

# Free-text patterns that look like secrets (bearer tokens, long hex/base64).
_SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9]{32,}\b"),
]

_MASK = "***REDACTED***"


def _redact(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor that removes sensitive data from every log event."""

    def scrub(value: Any) -> Any:
        if isinstance(value, str):
            for pattern in _SECRET_PATTERNS:
                value = pattern.sub(_MASK, value)
            return value
        if isinstance(value, dict):
            return {
                k: (_MASK if _SENSITIVE_KEYS.search(str(k)) else scrub(v))
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return type(value)(scrub(v) for v in value)
        return value

    for key in list(event_dict.keys()):
        if _SENSITIVE_KEYS.search(key):
            event_dict[key] = _MASK
        else:
            event_dict[key] = scrub(event_dict[key])
    return event_dict


def configure_logging() -> None:
    """Configure stdlib logging + structlog. Idempotent."""
    settings = get_settings()
    level = getattr(logging, settings.app.log_level.value, logging.INFO)
    is_local = settings.app.environment == Environment.LOCAL

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    # Quiet noisy third-party loggers.
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _redact,  # redaction runs before rendering
    ]

    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer(colors=True)
        if is_local
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)

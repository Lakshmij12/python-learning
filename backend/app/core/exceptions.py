"""Structured exception hierarchy.

Every error raised by the application derives from :class:`AppError`, carrying a
stable machine-readable ``code``, an HTTP ``status_code``, and an optional
safe-to-expose ``detail``. The API layer maps these to consistent JSON error
responses (see ``app.core.handlers``), so internal messages/stack traces never
leak to clients.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for all application errors."""

    code: str = "app_error"
    status_code: int = 500
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        detail: Any | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.detail = detail
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": {"code": self.code, "message": self.message}}
        if self.detail is not None:
            payload["error"]["detail"] = self.detail
        return payload


# --- 4xx --------------------------------------------------------------------


class ValidationAppError(AppError):
    code = "validation_error"
    status_code = 422
    message = "Request validation failed."


class AuthenticationError(AppError):
    code = "authentication_error"
    status_code = 401
    message = "Authentication required or credentials invalid."


class AuthorizationError(AppError):
    code = "authorization_error"
    status_code = 403
    message = "You are not permitted to perform this action."


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404
    message = "The requested resource was not found."


class ConflictError(AppError):
    code = "conflict"
    status_code = 409
    message = "The request conflicts with the current state."


class RateLimitError(AppError):
    code = "rate_limited"
    status_code = 429
    message = "Too many requests. Please slow down."


class WebhookVerificationError(AppError):
    code = "webhook_verification_failed"
    status_code = 403
    message = "Webhook signature verification failed."


class PromptInjectionError(AppError):
    code = "prompt_injection_detected"
    status_code = 400
    message = "Input was rejected by the safety filter."


# --- 5xx / integration ------------------------------------------------------


class ConfigurationError(AppError):
    code = "configuration_error"
    status_code = 500
    message = "The service is misconfigured."


class LLMProviderError(AppError):
    code = "llm_provider_error"
    status_code = 502
    message = "The AI provider returned an error."


class MessagingProviderError(AppError):
    code = "messaging_provider_error"
    status_code = 502
    message = "The messaging provider returned an error."

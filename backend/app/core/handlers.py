"""Exception handlers mapping errors to consistent JSON responses.

Application errors (``AppError``) render their stable code + safe message.
Unexpected exceptions return a generic 500 (details are logged, never leaked).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("app_error", code=exc.code, message=exc.message)
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "detail": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error=str(exc), error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "An internal error occurred."}},
        )

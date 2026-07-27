"""Redis-backed fixed-window rate limiting.

Limits requests per client (by API key, then client IP) using an atomic
INCR+EXPIRE window. Fails open if Redis is unavailable so a cache outage never
takes the API down; the webhook path is excluded (Meta manages its own retries).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config.settings import get_settings
from app.core.container import container
from app.core.logging import get_logger

logger = get_logger(__name__)

_EXCLUDED_PREFIXES = ("/webhook", "/health", "/docs", "/openapi", "/redoc")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:  # noqa: ANN001
        super().__init__(app)
        cfg = get_settings().security
        self._limit = cfg.rate_limit_requests
        self._window = cfg.rate_limit_window_seconds

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        if request.url.path.startswith(_EXCLUDED_PREFIXES):
            return await call_next(request)

        client_id = self._client_id(request)
        key = f"ratelimit:{client_id}:{request.url.path}"
        try:
            redis = container.redis
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, self._window)
            if count > self._limit:
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": "rate_limited", "message": "Too many requests."}},
                    headers={"Retry-After": str(self._window)},
                )
        except Exception:  # noqa: BLE001 - fail open on cache errors
            logger.warning("rate_limit.redis_unavailable")

        return await call_next(request)

    @staticmethod
    def _client_id(request: Request) -> str:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key[:12]}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

"""Health and readiness endpoints (unauthenticated, excluded from rate limits)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config.settings import get_settings
from app.core.container import container

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe — process is up."""
    return {"status": "ok", "environment": get_settings().app.environment.value}


@router.get("/health/ready")
async def ready() -> dict:
    """Readiness probe — dependencies reachable."""
    checks: dict[str, str] = {}

    try:
        redis_ok = await container.redis.ping()
        checks["redis"] = "ok" if redis_ok else "unreachable"
    except Exception:  # noqa: BLE001
        checks["redis"] = "unreachable"

    try:
        from sqlalchemy import text

        async with container.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "unreachable"

    ready = all(v == "ok" for v in checks.values())
    return {"status": "ready" if ready else "degraded", "checks": checks}

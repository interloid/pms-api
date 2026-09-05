import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import get_db
from app.schemas.common import BaseSchema

logger = logging.getLogger(__name__)

router = APIRouter()

DATABASE_CHECK_TIMEOUT_SECONDS = 10.0
CHECK_TIMEOUT_SECONDS = 2.0
DependencyStatus = Literal["up", "down"]


class HealthResponse(BaseSchema):
    status: Literal["ok"]
    message: str


class ReadinessChecks(BaseSchema):
    database: DependencyStatus
    redis: DependencyStatus


class ReadinessResponse(BaseSchema):
    status: Literal["ok", "not_ready"]
    checks: ReadinessChecks


async def check_database(db: AsyncSession) -> DependencyStatus:
    try:
        async with asyncio.timeout(
            DATABASE_CHECK_TIMEOUT_SECONDS,
        ):
            await db.execute(text("SELECT 1"))

        return "up"

    except TimeoutError:
        logger.warning(
            "Database readiness check timed out | timeout_seconds=%s",
            DATABASE_CHECK_TIMEOUT_SECONDS,
        )
        return "down"

    except Exception as exc:
        logger.exception(
            "Database readiness check failed | error_type=%s | error=%s",
            type(exc).__name__,
            str(exc),
        )
        return "down"


async def check_redis(redis: Redis) -> DependencyStatus:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            is_available = await redis.ping()

        return "up" if is_available else "down"

    except Exception:
        logger.exception("Redis readiness check failed")
        return "down"


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", message="Application is running")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database or Redis is unavailable",
            "model": ReadinessResponse,
        },
    },
)
async def ready(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ReadinessResponse:
    database_status, redis_status = await asyncio.gather(
        check_database(db),
        check_redis(redis),
    )

    checks = ReadinessChecks(database=database_status, redis=redis_status)

    is_ready = database_status == "up" and redis_status == "up"

    response.status_code = (
        status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    response.headers["Cache-Control"] = "no-store"

    return ReadinessResponse(
        status="ok" if is_ready else "not_ready",
        checks=checks,
    )

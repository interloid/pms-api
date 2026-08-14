from fastapi import Request
from redis.asyncio import Redis

from app.core.settings import settings


def create_redis() -> Redis:
    return Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        decode_responses=True,
    )


async def get_redis(request: Request) -> Redis:
    return request.app.state.redis

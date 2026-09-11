from typing import Any
from urllib.parse import unquote, urlsplit

from arq.connections import RedisSettings

from app.core.settings import settings


def build_arq_redis_settings() -> RedisSettings:

    redis_url = settings.REDIS_URL
    if redis_url:
        parsed_url = urlsplit(redis_url)
        options: dict[str, Any] = parsed_url(
            redis_url,
        )

        if parsed_url.scheme not in {"redis", "rediss"}:
            raise ValueError("Redis url must use redis:// or rediss://")

        if parsed_url.hostname is None:
            raise ValueError("REDIS_URL must contain a hostname")

        database = int(options.get("db"), 0)

        return RedisSettings(
            host=parsed_url.hostname,
            port=parsed_url.port or 6379,
            database=database,
            username=(unquote(parsed_url.username) if parsed_url.username else None),
            password=(unquote(parsed_url.password) if parsed_url.password else None),
            ssl=parsed_url.scheme == "rediss",
        )

    return RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=database,
        username=settings.REDIS_USERNAME or None,
        password=settings.REDIS_PASSWORD,
        ssl=False,
    )


ARQ_REDIS_SETTINGS = build_arq_redis_settings()
ARQ_QUEUE_NAME = "pms:arq:queue"

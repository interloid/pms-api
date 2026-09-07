from contextlib import AsyncExitStack, asynccontextmanager

import aioboto3
from fastapi import FastAPI

from app.core.settings import settings
from app.db.redis import create_redis


@asynccontextmanager
async def lifespan(app: FastAPI):

    redis = create_redis()

    async with AsyncExitStack() as stack:
        try:
            await redis.ping()
            app.state.redis = redis

            session = aioboto3.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=(
                    settings.AWS_SECRET_ACCESS_KEY.get_secret_value()
                    if settings.AWS_SECRET_ACCESS_KEY is not None
                    else None
                ),
            )
            s3_client = await stack.enter_async_context(
                session.client("s3", region_name=settings.AWS_REGION)
            )
            app.state.s3 = s3_client

            yield

        finally:
            await redis.aclose()

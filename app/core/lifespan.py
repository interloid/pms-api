from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.redis import create_redis


@asynccontextmanager
async def lifespan(app: FastAPI):

    redis = create_redis()

    try:
        await redis.ping()
        app.state.redis = redis

        yield

    finally:
        await redis.aclose()

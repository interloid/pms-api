import secrets

from redis.asyncio import Redis

from app.core.security import hash_passcode
from app.core.settings import settings


def generate_passcode() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def get_passcode_key(email: str) -> str:
    return f"auth:passcode:{email}"


def get_passcode_attempt_key(email: str) -> str:
    return f"auth:passcode:attempts:{email}"


async def store_passcode(redis: Redis, email: str, passcode: str) -> None:

    passcode_hash = hash_passcode(passcode)

    key = get_passcode_key(email)

    await redis.set(key, passcode_hash, ex=settings.PASSCODE_EXPIRE_SECONDS)


async def get_passcode(redis: Redis, email: str) -> str | None:

    key = get_passcode_key(email)
    return await redis.get(key)


async def delete_passcode(redis: Redis, email: str) -> None:

    key = get_passcode_key(email)
    await redis.delete(key)


async def get_passcode_attempts(redis: Redis, email: str) -> int:

    key = get_passcode_attempt_key(email)
    attempts = await redis.get(key)

    if attempts is None:
        return 0

    return int(attempts)


async def increment_passcode_attempts(redis: Redis, email: str) -> int:

    key = get_passcode_attempt_key(email)
    attempts = await redis.incr(key)

    await redis.expire(key, settings.PASSCODE_EXPIRE_SECONDS)
    return attempts


async def delete_passcode_attempts(redis: Redis, email: str) -> None:

    key = get_passcode_attempt_key(email)
    await redis.delete(key)


async def reset_passcode_attempts(redis: Redis, email: str) -> None:

    key = get_passcode_attempt_key(email)
    await redis.delete(key)

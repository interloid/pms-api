from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.passcode import (
    delete_passcode,
    generate_passcode,
    get_passcode,
    get_passcode_attempt_key,
    get_passcode_attempts,
    get_passcode_key,
    increment_passcode_attempts,
    reset_passcode_attempts,
    store_passcode,
)
from app.core.settings import settings


def test_generate_passcode_returns_six_digit_string():
    passcode = generate_passcode()

    assert isinstance(passcode, str)
    assert len(passcode) == 6
    assert passcode.isdigit()


def test_generate_passcode_preserves_leading_zeroes():
    with patch(
        "app.core.passcode.secrets.randbelow",
        return_value=123,
    ):
        passcode = generate_passcode()

    assert passcode == "000123"


def test_get_passcode_key():
    email = "user@example.com"

    result = get_passcode_key(email)

    assert result == "auth:passcode:user@example.com"


def test_get_passcode_attempt_key():
    email = "user@example.com"

    result = get_passcode_attempt_key(email)

    assert result == "auth:passcode:attempts:user@example.com"


@pytest.mark.asyncio
async def test_store_passcode():
    redis = MagicMock()
    redis.set = AsyncMock()

    email = "user@example.com"
    passcode = "123456"

    with patch(
        "app.core.passcode.hash_passcode",
        return_value="hashed-passcode",
    ) as mock_hash:
        result = await store_passcode(
            redis=redis,
            email=email,
            passcode=passcode,
        )

    assert result is None

    mock_hash.assert_called_once_with(passcode)

    redis.set.assert_awaited_once_with(
        "auth:passcode:user@example.com",
        "hashed-passcode",
        ex=settings.PASSCODE_EXPIRE_SECONDS,
    )


@pytest.mark.asyncio
async def test_get_passcode_returns_stored_passcode():
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value="hashed-passcode",
    )

    result = await get_passcode(
        redis=redis,
        email="user@example.com",
    )

    assert result == "hashed-passcode"

    redis.get.assert_awaited_once_with(
        "auth:passcode:user@example.com",
    )


@pytest.mark.asyncio
async def test_get_passcode_returns_none_when_not_found():
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value=None,
    )

    result = await get_passcode(
        redis=redis,
        email="user@example.com",
    )

    assert result is None

    redis.get.assert_awaited_once_with(
        "auth:passcode:user@example.com",
    )


@pytest.mark.asyncio
async def test_delete_passcode():
    redis = MagicMock()
    redis.delete = AsyncMock()

    result = await delete_passcode(
        redis=redis,
        email="user@example.com",
    )

    assert result is None

    redis.delete.assert_awaited_once_with(
        "auth:passcode:user@example.com",
    )


@pytest.mark.asyncio
async def test_get_passcode_attempts_returns_zero_when_not_found():
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value=None,
    )

    result = await get_passcode_attempts(
        redis=redis,
        email="user@example.com",
    )

    assert result == 0

    redis.get.assert_awaited_once_with(
        "auth:passcode:attempts:user@example.com",
    )


@pytest.mark.asyncio
async def test_get_passcode_attempts_returns_attempt_count():
    redis = MagicMock()
    redis.get = AsyncMock(
        return_value="3",
    )

    result = await get_passcode_attempts(
        redis=redis,
        email="user@example.com",
    )

    assert result == 3

    redis.get.assert_awaited_once_with(
        "auth:passcode:attempts:user@example.com",
    )


@pytest.mark.asyncio
async def test_increment_passcode_attempts():
    redis = MagicMock()

    redis.incr = AsyncMock(
        return_value=3,
    )
    redis.expire = AsyncMock()

    result = await increment_passcode_attempts(
        redis=redis,
        email="user@example.com",
    )

    assert result == 3

    redis.incr.assert_awaited_once_with(
        "auth:passcode:attempts:user@example.com",
    )

    redis.expire.assert_awaited_once_with(
        "auth:passcode:attempts:user@example.com",
        settings.PASSCODE_EXPIRE_SECONDS,
    )



@pytest.mark.asyncio
async def test_reset_passcode_attempts():
    redis = MagicMock()
    redis.delete = AsyncMock()

    result = await reset_passcode_attempts(
        redis=redis,
        email="user@example.com",
    )

    assert result is None

    redis.delete.assert_awaited_once_with(
        "auth:passcode:attempts:user@example.com",
    )

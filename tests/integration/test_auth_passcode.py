import hashlib
import hmac
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleEnum
from app.core.security import hash_refresh_token
from app.core.settings import settings
from app.main import app
from app.models.refresh_token_model import RefreshToken
from app.models.user_model import User


def get_passcode_key(email: str) -> str:
    return f"auth:passcode:{email.strip().lower()}"


def get_attempts_key(email: str) -> str:
    return f"auth:passcode:attempts:{email.strip().lower()}"


def hash_test_passcode(passcode: str) -> str:
    pepper = settings.PASSCODE_PEPPER.get_secret_value()

    return hmac.new(
        pepper.encode("utf-8"),
        passcode.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def store_test_passcode(
    email: str,
    passcode: str,
) -> None:
    redis = app.state.redis

    await redis.set(
        get_passcode_key(email),
        hash_test_passcode(passcode),
        ex=300,
    )


async def delete_test_passcode_keys() -> None:
    redis = app.state.redis

    async for key in redis.scan_iter(
        match="auth:passcode:*",
    ):
        await redis.delete(key)


@pytest_asyncio.fixture(autouse=True)
async def clean_passcode_redis(
    client: AsyncClient,
) -> AsyncIterator[None]:
    await delete_test_passcode_keys()

    yield

    await delete_test_passcode_keys()


@pytest.mark.parametrize(
    "passcode",
    [
        "12345",
        "1234567",
        "abcdef",
    ],
    ids=[
        "too-short",
        "too-long",
        "not-numeric",
    ],
)
@pytest.mark.asyncio
async def test_passcode_validation_error(
    client: AsyncClient,
    passcode: str,
) -> None:
    response = await client.post(
        "/api/v1/auth/passcode/verifications",
        json={
            "email": "validation@example.com",
            "passcode": passcode,
        },
    )

    assert response.status_code == 422

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_missing_passcode_returns_unauthorized(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/passcode/verifications",
        json={
            "email": "missing@example.com",
            "passcode": "123456",
        },
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_incorrect_passcode_increments_attempts(
    client: AsyncClient,
) -> None:
    email = f"incorrect-{uuid4()}@example.com"

    await store_test_passcode(
        email,
        "123456",
    )

    response = await client.post(
        "/api/v1/auth/passcode/verifications",
        json={
            "email": email,
            "passcode": "654321",
        },
    )

    assert response.status_code == 401

    redis = app.state.redis

    attempts = await redis.get(
        get_attempts_key(email),
    )
    stored_passcode = await redis.get(
        get_passcode_key(email),
    )

    assert attempts is not None
    assert int(attempts) == 1
    assert stored_passcode is not None

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_maximum_passcode_attempts_returns_too_many_requests(
    client: AsyncClient,
) -> None:
    email = f"attempts-{uuid4()}@example.com"

    await store_test_passcode(
        email,
        "123456",
    )

    max_attempts = settings.PASSCODE_MAX_ATTEMPTS

    for attempt_number in range(1, max_attempts + 1):
        response = await client.post(
            "/api/v1/auth/passcode/verifications",
            json={
                "email": email,
                "passcode": "654321",
            },
        )

        if attempt_number < max_attempts:
            assert response.status_code == 401
        else:
            assert response.status_code == 429

    blocked_response = await client.post(
        "/api/v1/auth/passcode/verifications",
        json={
            "email": email,
            "passcode": "123456",
        },
    )

    assert blocked_response.status_code == 429

    response_data = blocked_response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "TOO_MANY_REQUESTS"
    assert response_data["error"]["details"]["remaining_attempts"] == 0


@pytest.mark.asyncio
async def test_inactive_user_cannot_login_with_passcode(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"inactive-{uuid4()}@example.com"

    user = User(
        email=email,
        hashed_password=None,
        first_name="Inactive",
        last_name="User",
        is_active=False,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    await store_test_passcode(
        email,
        "123456",
    )

    response = await client.post(
        "/api/v1/auth/passcode/verifications",
        json={
            "email": email,
            "passcode": "123456",
        },
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_existing_user_can_login_with_passcode(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"existing-{uuid4()}@example.com"
    passcode = "123456"

    user = User(
        email=email,
        hashed_password=None,
        first_name="Existing",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    await store_test_passcode(
        email,
        passcode,
    )

    response = await client.post(
        "/api/v1/auth/passcode/verifications",
        json={
            "email": email,
            "passcode": passcode,
        },
    )

    assert response.status_code == 200

    response_data = response.json()
    token_data = response_data["data"]

    assert response_data["success"] is True
    assert response_data["message"] == "Login successful"
    assert token_data["access_token"]
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["id"] == str(user.id)
    assert token_data["user"]["email"] == email

    raw_refresh_token = response.cookies.get(
        settings.REFRESH_TOKEN_COOKIE_NAME,
    )

    assert raw_refresh_token is not None

    redis = app.state.redis

    assert await redis.get(get_passcode_key(email)) is None
    assert await redis.get(get_attempts_key(email)) is None

    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
        )
    )

    stored_token = result.scalar_one_or_none()

    assert stored_token is not None
    assert stored_token.is_revoked is False
    assert stored_token.token_hash == hash_refresh_token(raw_refresh_token)


@pytest.mark.asyncio
async def test_passcode_login_creates_new_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"new-passcode-{uuid4()}@example.com"
    passcode = "123456"

    existing_result = await db_session.execute(
        select(User).where(
            User.email == email,
        )
    )

    assert existing_result.scalar_one_or_none() is None

    await store_test_passcode(
        email,
        passcode,
    )

    response = await client.post(
        "/api/v1/auth/passcode/verifications",
        json={
            "email": email,
            "passcode": passcode,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["success"] is True
    assert response_data["data"]["access_token"]
    assert response_data["data"]["user"]["email"] == email

    result = await db_session.execute(
        select(User).where(
            User.email == email,
        )
    )

    created_user = result.scalar_one_or_none()

    assert created_user is not None
    assert created_user.is_active is True
    assert created_user.role == RoleEnum.VIEWER

    token_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == created_user.id,
        )
    )

    stored_token = token_result.scalar_one_or_none()

    assert stored_token is not None
    assert stored_token.is_revoked is False

    redis = app.state.redis

    assert await redis.get(get_passcode_key(email)) is None
    assert await redis.get(get_attempts_key(email)) is None


@pytest.mark.asyncio
async def test_passcode_can_only_be_used_once(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"one-time-{uuid4()}@example.com"
    passcode = "123456"

    user = User(
        email=email,
        hashed_password=None,
        first_name="One",
        last_name="Time",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    await store_test_passcode(
        email,
        passcode,
    )

    first_response = await client.post(
        "/api/v1/auth/passcode/verifications",
        json={
            "email": email,
            "passcode": passcode,
        },
    )

    assert first_response.status_code == 200

    second_response = await client.post(
        "/api/v1/auth/passcode/verifications",
        json={
            "email": email,
            "passcode": passcode,
        },
    )

    assert second_response.status_code == 401

    response_data = second_response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleEnum
from app.core.passcode import get_passcode
from app.core.security import verify_passcode
from app.core.settings import settings
from app.main import app
from app.models.user_model import User


def passcode_key(email: str) -> str:
    return f"auth:passcode:{email.strip().lower()}"


@pytest_asyncio.fixture(autouse=True)
async def clean_test_redis(
    client: AsyncClient,
) -> AsyncIterator[None]:
    redis = app.state.redis

    connection_options = redis.connection_pool.connection_kwargs
    redis_host = connection_options.get("host")

    if redis_host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError(
            "Passcode tests must use local test Redis",
        )

    await redis.flushdb()

    try:
        yield
    finally:
        await redis.flushdb()


@pytest.fixture
def sent_emails(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:
    captured_emails: list[dict[str, Any]] = []

    async def fake_send_passcode_email(
        *,
        to_email: str,
        first_name: str,
        passcode: str,
        expiry_minutes: int,
    ) -> None:
        captured_emails.append(
            {
                "to_email": to_email,
                "first_name": first_name,
                "passcode": passcode,
                "expiry_minutes": expiry_minutes,
            }
        )

    monkeypatch.setattr(
        "app.services.auth_service.send_passcode_email",
        fake_send_passcode_email,
    )

    return captured_emails


@pytest.mark.asyncio
async def test_request_passcode_with_invalid_email(
    client: AsyncClient,
    sent_emails: list[dict[str, Any]],
) -> None:
    response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": "invalid-email",
        },
    )

    assert response.status_code == 422
    assert sent_emails == []

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_request_passcode_for_new_user(
    client: AsyncClient,
    sent_emails: list[dict[str, Any]],
) -> None:
    email = f"new-{uuid4()}@example.com"

    response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": email,
        },
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["success"] is True
    assert (
        response_data["message"] == "Verification code sent to the email is registered."
    )

    assert len(sent_emails) == 1

    captured_email = sent_emails[0]

    assert captured_email["to_email"] == email
    assert captured_email["first_name"] == "User"
    assert captured_email["expiry_minutes"] == 5

    generated_passcode = captured_email["passcode"]

    assert isinstance(generated_passcode, str)
    assert len(generated_passcode) == settings.PASSCODE_LENGTH
    assert generated_passcode.isdigit()

    redis = app.state.redis

    stored_hash = await get_passcode(
        redis=redis,
        email=email,
    )

    assert stored_hash is not None
    assert stored_hash != generated_passcode
    assert verify_passcode(
        generated_passcode,
        stored_hash,
    )

    ttl = await redis.ttl(
        passcode_key(email),
    )

    assert 0 < ttl <= settings.PASSCODE_EXPIRE_SECONDS


@pytest.mark.asyncio
async def test_request_passcode_for_existing_user_uses_first_name(
    client: AsyncClient,
    db_session: AsyncSession,
    sent_emails: list[dict[str, Any]],
) -> None:
    email = f"existing-{uuid4()}@example.com"

    user = User(
        email=email,
        hashed_password=None,
        first_name="Sparrow",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": email,
        },
    )

    assert response.status_code == 200
    assert len(sent_emails) == 1

    captured_email = sent_emails[0]

    assert captured_email["to_email"] == email
    assert captured_email["first_name"] == "Sparrow"


@pytest.mark.asyncio
async def test_registered_and_unregistered_responses_are_generic(
    client: AsyncClient,
    db_session: AsyncSession,
    sent_emails: list[dict[str, Any]],
) -> None:
    registered_email = f"registered-{uuid4()}@example.com"
    unregistered_email = f"unregistered-{uuid4()}@example.com"

    user = User(
        email=registered_email,
        hashed_password=None,
        first_name="Registered",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    registered_response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": registered_email,
        },
    )
    unregistered_response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": unregistered_email,
        },
    )

    assert registered_response.status_code == 200
    assert unregistered_response.status_code == 200

    assert (
        registered_response.json()["message"] == unregistered_response.json()["message"]
    )

    assert len(sent_emails) == 2


@pytest.mark.asyncio
async def test_inactive_user_cannot_request_passcode(
    client: AsyncClient,
    db_session: AsyncSession,
    sent_emails: list[dict[str, Any]],
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

    response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": email,
        },
    )

    assert response.status_code == 401
    assert sent_emails == []

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"

    stored_hash = await get_passcode(
        redis=app.state.redis,
        email=email,
    )

    assert stored_hash is None


@pytest.mark.asyncio
async def test_new_request_replaces_previous_passcode(
    client: AsyncClient,
    sent_emails: list[dict[str, Any]],
) -> None:
    email = f"replace-{uuid4()}@example.com"

    first_response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": email,
        },
    )
    second_response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": email,
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(sent_emails) == 2

    latest_passcode = sent_emails[-1]["passcode"]

    stored_hash = await get_passcode(
        redis=app.state.redis,
        email=email,
    )

    assert stored_hash is not None
    assert verify_passcode(
        latest_passcode,
        stored_hash,
    )


@pytest.mark.asyncio
async def test_passcode_email_rate_limit(
    client: AsyncClient,
    sent_emails: list[dict[str, Any]],
) -> None:
    email = f"email-limit-{uuid4()}@example.com"

    for _ in range(
        settings.PASSCODE_REQUEST_EMAIL_LIMIT,
    ):
        response = await client.post(
            "/api/v1/auth/passcode/request",
            json={
                "email": email,
            },
        )

        assert response.status_code == 200

    blocked_response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": email,
        },
    )

    assert blocked_response.status_code == 429

    response_data = blocked_response.json()

    assert response_data["success"] is False
    assert len(sent_emails) == (settings.PASSCODE_REQUEST_EMAIL_LIMIT)


@pytest.mark.asyncio
async def test_passcode_ip_rate_limit(
    client: AsyncClient,
    sent_emails: list[dict[str, Any]],
) -> None:
    unique_value = uuid4().hex[:8]

    for index in range(
        settings.PASSCODE_REQUEST_IP_LIMIT,
    ):
        response = await client.post(
            "/api/v1/auth/passcode/request",
            json={
                "email": (f"ip-limit-{index}-{unique_value}@example.com"),
            },
        )

        assert response.status_code == 200

    blocked_response = await client.post(
        "/api/v1/auth/passcode/request",
        json={
            "email": (f"ip-limit-blocked-{unique_value}@example.com"),
        },
    )

    assert blocked_response.status_code == 429

    response_data = blocked_response.json()

    assert response_data["success"] is False
    assert len(sent_emails) == (settings.PASSCODE_REQUEST_IP_LIMIT)

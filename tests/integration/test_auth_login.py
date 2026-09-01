from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleEnum
from app.core.security import hash_password
from app.core.settings import settings
from app.models.refresh_token_model import RefreshToken
from app.models.user_model import User


@pytest.mark.asyncio
async def test_login_with_unknown_email_returns_unauthorized(
    client: AsyncClient,
) -> None:
    login_data = {
        "email": "missing-user@example.com",
        "password": "InvalidPassword123!",
        "remember_me": False,
    }

    response = await client.post("/api/v1/auth/login", json=login_data)

    assert response.status_code == 401
    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"user-{uuid4()}@example.com"

    user = User(
        email=email,
        hashed_password=hash_password("CorrectPassword123!"),
        first_name="Test",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    login_data = {
        "email": email,
        "password": "WrongPassword123!",
        "remember_me": False,
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_with_inactive_user_returns_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"inactive-{uuid4()}@example.com"
    password = "CorrectPassword123!"

    user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name="Inactive",
        last_name="User",
        is_active=False,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    login_data = {
        "email": email,
        "password": password,
        "remember_me": False,
    }

    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_passwordless_user_cannot_use_password_login(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"passwordless-{uuid4()}@example.com"

    user = User(
        email=email,
        hashed_password=None,
        first_name="Passwordless",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "SomePassword123!",
            "remember_me": False,
        },
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["message"] == "Invalid email or password"


@pytest.mark.parametrize(
    "login_data",
    [
        {
            "email": "invalid-email",
            "password": "ValidPassword123!",
            "remember_me": False,
        },
        {
            "email": "user@example.com",
            "password": "short",
            "remember_me": False,
        },
        {
            "email": "user@example.com",
            "remember_me": False,
        },
    ],
    ids=[
        "invalid-email",
        "short-password",
        "missing-password",
    ],
)
@pytest.mark.asyncio
async def test_login_validation_errors(
    client: AsyncClient,
    login_data: dict,
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert response.status_code == 422

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_successful_password_login(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"login-{uuid4()}@example.com"
    password = "CorrectPassword123!"

    user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name="Login",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
            "remember_me": False,
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

    refresh_cookie = response.cookies.get(
        settings.REFRESH_TOKEN_COOKIE_NAME,
    )

    assert refresh_cookie is not None

    set_cookie_header = response.headers["set-cookie"].lower()

    assert "httponly" in set_cookie_header
    assert "secure" in set_cookie_header
    assert "samesite=none" in set_cookie_header

    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
        )
    )

    stored_tokens = result.scalars().all()

    assert len(stored_tokens) == 1
    assert stored_tokens[0].is_revoked is False
    assert stored_tokens[0].family_id is not None
    assert stored_tokens[0].expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_login_access_token_can_access_me(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"access-token-{uuid4()}@example.com"
    password = "CorrectPassword123!"

    user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name="Access",
        last_name="Token",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
            "remember_me": False,
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["data"]["access_token"]

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert me_response.status_code == 200

    me_data = me_response.json()

    assert me_data["data"]["id"] == str(user.id)
    assert me_data["data"]["email"] == email


@pytest.mark.asyncio
async def test_multiple_logins_create_separate_token_families(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = f"multiple-login-{uuid4()}@example.com"
    password = "CorrectPassword123!"

    user = User(
        email=email,
        hashed_password=hash_password(password),
        first_name="Multiple",
        last_name="Devices",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    login_data = {
        "email": email,
        "password": password,
        "remember_me": False,
    }

    first_response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )
    second_response = await client.post(
        "/api/v1/auth/login",
        json=login_data,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
        )
    )

    stored_tokens = result.scalars().all()

    assert len(stored_tokens) == 2
    assert len({token.family_id for token in stored_tokens}) == 2
    assert all(token.is_revoked is False for token in stored_tokens)


@pytest.mark.asyncio
async def test_remember_me_creates_longer_refresh_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    password = "CorrectPassword123!"

    normal_user = User(
        email=f"normal-{uuid4()}@example.com",
        hashed_password=hash_password(password),
        first_name="Normal",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    remember_user = User(
        email=f"remember-{uuid4()}@example.com",
        hashed_password=hash_password(password),
        first_name="Remember",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add_all([normal_user, remember_user])
    await db_session.commit()

    normal_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": normal_user.email,
            "password": password,
            "remember_me": False,
        },
    )

    remember_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": remember_user.email,
            "password": password,
            "remember_me": True,
        },
    )

    assert normal_response.status_code == 200
    assert remember_response.status_code == 200

    normal_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == normal_user.id,
        )
    )
    remember_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == remember_user.id,
        )
    )

    normal_token = normal_result.scalar_one()
    remember_token = remember_result.scalar_one()

    assert remember_token.expires_at > normal_token.expires_at

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleEnum
from app.core.security import hash_password, hash_refresh_token
from app.core.settings import settings
from app.models.refresh_token_model import RefreshToken
from app.models.user_model import User


async def create_user_and_login(
    client: AsyncClient,
    db_session: AsyncSession,
) -> tuple[User, str]:
    password = "CorrectPassword123!"

    user = User(
        email=f"refresh-{uuid4()}@example.com",
        hashed_password=hash_password(password),
        first_name="Refresh",
        last_name="User",
        is_active=True,
        role=RoleEnum.VIEWER,
    )

    db_session.add(user)
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": password,
            "remember_me": False,
        },
    )

    assert response.status_code == 200

    raw_refresh_token = response.cookies.get(
        settings.REFRESH_TOKEN_COOKIE_NAME,
    )

    assert raw_refresh_token is not None

    return user, raw_refresh_token


async def get_stored_refresh_token(
    db_session: AsyncSession,
    raw_refresh_token: str,
) -> RefreshToken:
    token_hash = hash_refresh_token(raw_refresh_token)

    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
        )
    )

    stored_token = result.scalar_one_or_none()

    assert stored_token is not None

    return stored_token


def refresh_cookie_header(
    raw_refresh_token: str,
) -> dict[str, str]:
    return {"Cookie": (f"{settings.REFRESH_TOKEN_COOKIE_NAME}={raw_refresh_token}")}


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_unauthorized(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/refresh",
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_refresh_with_unknown_token_returns_unauthorized(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/refresh",
        headers=refresh_cookie_header(
            "unknown-refresh-token",
        ),
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_refresh_with_revoked_token_returns_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, raw_refresh_token = await create_user_and_login(
        client,
        db_session,
    )

    stored_token = await get_stored_refresh_token(
        db_session,
        raw_refresh_token,
    )

    stored_token.is_revoked = True
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=refresh_cookie_header(raw_refresh_token),
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_refresh_with_expired_token_returns_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, raw_refresh_token = await create_user_and_login(
        client,
        db_session,
    )

    stored_token = await get_stored_refresh_token(
        db_session,
        raw_refresh_token,
    )

    stored_token.expires_at = datetime.now(UTC) - timedelta(
        seconds=1,
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=refresh_cookie_header(raw_refresh_token),
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_refresh_for_inactive_user_returns_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user, raw_refresh_token = await create_user_and_login(
        client,
        db_session,
    )

    user.is_active = False
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=refresh_cookie_header(raw_refresh_token),
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_successful_refresh_rotates_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user, old_raw_token = await create_user_and_login(
        client,
        db_session,
    )

    old_stored_token = await get_stored_refresh_token(
        db_session,
        old_raw_token,
    )
    family_id = old_stored_token.family_id

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=refresh_cookie_header(old_raw_token),
    )

    assert response.status_code == 200

    response_data = response.json()
    token_data = response_data["data"]

    assert response_data["success"] is True
    assert token_data["access_token"]
    assert token_data["token_type"] == "bearer"

    new_raw_token = response.cookies.get(
        settings.REFRESH_TOKEN_COOKIE_NAME,
    )

    assert new_raw_token is not None
    assert new_raw_token != old_raw_token

    await db_session.refresh(old_stored_token)

    assert old_stored_token.is_revoked is True

    new_stored_token = await get_stored_refresh_token(
        db_session,
        new_raw_token,
    )

    assert new_stored_token.user_id == user.id
    assert new_stored_token.family_id == family_id
    assert new_stored_token.is_revoked is False
    assert new_stored_token.expires_at > datetime.now(UTC)

    cookie_header = response.headers["set-cookie"].lower()

    assert "httponly" in cookie_header
    assert "secure" in cookie_header
    assert "samesite=none" in cookie_header

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": (f"Bearer {token_data['access_token']}")},
    )

    assert me_response.status_code == 200
    assert me_response.json()["data"]["id"] == str(user.id)


@pytest.mark.asyncio
async def test_reusing_rotated_token_revokes_family(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _, old_raw_token = await create_user_and_login(
        client,
        db_session,
    )

    old_stored_token = await get_stored_refresh_token(
        db_session,
        old_raw_token,
    )
    family_id = old_stored_token.family_id

    first_refresh = await client.post(
        "/api/v1/auth/refresh",
        headers=refresh_cookie_header(old_raw_token),
    )

    assert first_refresh.status_code == 200

    reuse_response = await client.post(
        "/api/v1/auth/refresh",
        headers=refresh_cookie_header(old_raw_token),
    )

    assert reuse_response.status_code == 401

    db_session.expire_all()

    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id,
        )
    )

    family_tokens = result.scalars().all()

    assert len(family_tokens) == 2
    assert all(token.is_revoked is True for token in family_tokens)


@pytest.mark.asyncio
async def test_reuse_attack_does_not_revoke_other_device(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user, first_raw_token = await create_user_and_login(
        client,
        db_session,
    )

    second_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "CorrectPassword123!",
            "remember_me": False,
        },
    )

    assert second_login.status_code == 200

    second_raw_token = second_login.cookies.get(
        settings.REFRESH_TOKEN_COOKIE_NAME,
    )

    assert second_raw_token is not None
    assert second_raw_token != first_raw_token

    second_device_token = await get_stored_refresh_token(
        db_session,
        second_raw_token,
    )

    first_refresh = await client.post(
        "/api/v1/auth/refresh",
        headers=refresh_cookie_header(first_raw_token),
    )

    assert first_refresh.status_code == 200

    reuse_response = await client.post(
        "/api/v1/auth/refresh",
        headers=refresh_cookie_header(first_raw_token),
    )

    assert reuse_response.status_code == 401

    await db_session.refresh(second_device_token)

    assert second_device_token.is_revoked is False

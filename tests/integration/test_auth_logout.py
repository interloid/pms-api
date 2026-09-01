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
) -> tuple[User, str, str]:
    password = "CorrectPassword123!"

    user = User(
        email=f"logout-{uuid4()}@example.com",
        hashed_password=hash_password(password),
        first_name="Logout",
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

    response_data = response.json()["data"]
    access_token = response_data["access_token"]

    raw_refresh_token = response.cookies.get(
        settings.REFRESH_TOKEN_COOKIE_NAME,
    )

    assert raw_refresh_token is not None

    return user, access_token, raw_refresh_token


async def login_existing_user(
    client: AsyncClient,
    user: User,
) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "CorrectPassword123!",
            "remember_me": False,
        },
    )

    assert response.status_code == 200

    raw_refresh_token = response.cookies.get(
        settings.REFRESH_TOKEN_COOKIE_NAME,
    )

    assert raw_refresh_token is not None

    return raw_refresh_token


async def get_stored_token(
    db_session: AsyncSession,
    raw_refresh_token: str,
) -> RefreshToken:
    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(raw_refresh_token),
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
async def test_logout_without_cookie_is_successful(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/logout",
    )

    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.asyncio
async def test_logout_with_unknown_cookie_is_successful(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/logout",
        headers=refresh_cookie_header(
            "unknown-refresh-token",
        ),
    )

    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.asyncio
async def test_logout_current_device_revokes_only_current_family(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user, _, first_raw_token = await create_user_and_login(
        client,
        db_session,
    )

    second_raw_token = await login_existing_user(
        client,
        user,
    )

    first_stored_token = await get_stored_token(
        db_session,
        first_raw_token,
    )
    second_stored_token = await get_stored_token(
        db_session,
        second_raw_token,
    )

    assert first_stored_token.family_id != second_stored_token.family_id

    response = await client.post(
        "/api/v1/auth/logout",
        headers=refresh_cookie_header(first_raw_token),
    )

    assert response.status_code == 204
    assert response.content == b""

    db_session.expire_all()

    await db_session.refresh(first_stored_token)
    await db_session.refresh(second_stored_token)

    assert first_stored_token.is_revoked is True
    assert second_stored_token.is_revoked is False

    set_cookie_header = response.headers["set-cookie"].lower()

    assert settings.REFRESH_TOKEN_COOKIE_NAME.lower() in (set_cookie_header)
    assert "max-age=0" in set_cookie_header


@pytest.mark.asyncio
async def test_logout_does_not_immediately_invalidate_access_token(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user, access_token, raw_refresh_token = await create_user_and_login(
        client,
        db_session,
    )

    logout_response = await client.post(
        "/api/v1/auth/logout",
        headers=refresh_cookie_header(raw_refresh_token),
    )

    assert logout_response.status_code == 204

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert me_response.status_code == 200
    assert me_response.json()["data"]["id"] == str(user.id)


@pytest.mark.asyncio
async def test_logout_all_requires_access_token(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/logout-all",
    )

    assert response.status_code == 401

    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_logout_all_revokes_every_user_family(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user, access_token, first_raw_token = await create_user_and_login(
        client,
        db_session,
    )

    second_raw_token = await login_existing_user(
        client,
        user,
    )

    response = await client.post(
        "/api/v1/auth/logout-all",
        headers={
            "Authorization": f"Bearer {access_token}",
            **refresh_cookie_header(second_raw_token),
        },
    )

    assert response.status_code == 204
    assert response.content == b""

    user_id = user.id
    db_session.expire_all()

    result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
        )
    )

    stored_tokens = result.scalars().all()

    assert len(stored_tokens) == 2
    assert all(token.is_revoked is True for token in stored_tokens)

    first_token = await get_stored_token(
        db_session,
        first_raw_token,
    )
    second_token = await get_stored_token(
        db_session,
        second_raw_token,
    )

    assert first_token.is_revoked is True
    assert second_token.is_revoked is True


@pytest.mark.asyncio
async def test_logout_all_does_not_revoke_other_users_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user_a, access_token_a, _ = await create_user_and_login(
        client,
        db_session,
    )
    user_b, _, _ = await create_user_and_login(
        client,
        db_session,
    )

    user_a_id = user_a.id
    user_b_id = user_b.id

    response = await client.post(
        "/api/v1/auth/logout-all",
        headers={
            "Authorization": f"Bearer {access_token_a}",
        },
    )

    assert response.status_code == 204

    db_session.expire_all()

    user_a_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_a_id,
        )
    )
    user_b_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_b_id,
        )
    )

    user_a_tokens = user_a_result.scalars().all()
    user_b_tokens = user_b_result.scalars().all()

    assert len(user_a_tokens) == 1
    assert all(token.is_revoked is True for token in user_a_tokens)

    assert len(user_b_tokens) == 1
    assert all(token.is_revoked is False for token in user_b_tokens)

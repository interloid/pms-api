from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user_model import User


@pytest.mark.asyncio
async def test_get_me_without_access_token(client: AsyncClient) -> None:

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["message"] == "Authentication required"


@pytest.mark.asyncio
async def test_get_me_with_invalid_token(client: AsyncClient) -> None:

    headers = {"Authorization": "Bearer invalid-token"}
    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["message"] == "Invalid access token"


@pytest.mark.asyncio
async def test_get_me_with_missing_user(client: AsyncClient) -> None:
    missing_user_id = uuid4()
    access_token = create_access_token({"sub": str(missing_user_id)})

    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["message"] == "Invalid access token"


@pytest.mark.asyncio
async def test_get_me_with_inactive_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:

    user = User(
        email=f"inactive-{uuid4()}@example.com",
        first_name="Inactive",
        last_name="User",
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    access_token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 401
    response_data = response.json()

    assert response_data["success"] is False
    assert response_data["message"] == "Invalid access token"


@pytest.mark.asyncio
async def test_get_me_with_active_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:

    user = User(
        email=f"active-{uuid4()}@example.com",
        first_name="Active",
        last_name="User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    access_token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    response_data = response.json()

    assert response_data["success"] is True
    assert response_data["data"]["id"] == str(user.id)
    assert response_data["data"]["email"] == user.email
    assert response_data["message"] == "Current user retrieved successfully"

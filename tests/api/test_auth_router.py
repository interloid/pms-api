from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI

from app.api.dependencies import get_current_user
from app.api.v1.endpoints.auth_router import router as auth_router
from app.api.v1.endpoints.email_router import router as email_router
from app.api.v1.endpoints.oauth_router import router as oauth_router
from app.core.constants import RoleEnum
from app.core.settings import settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.exceptions.custom import InternalServerException
from app.schemas.auth_schema import LoginResponse
from app.schemas.response import ApiResponse
from app.schemas.user_schema import UserResponse
from tests.api.conftest import ApiClient

REFRESH_TOKEN = "raw-refresh-token"
REFRESH_MAX_AGE = 604800


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(email_router)
    app.include_router(oauth_router)

    async def dependency():
        return object()

    app.dependency_overrides[get_db] = dependency
    app.dependency_overrides[get_redis] = dependency
    return ApiClient(app)


def login_result():
    result = ApiResponse[LoginResponse](
        message="Login successful",
        data=LoginResponse(
            access_token="access-token",
            expires_in=1800,
            user=UserResponse(
                id=uuid4(),
                email="user@example.com",
                first_name="Test",
                last_name="User",
                is_active=True,
                role=RoleEnum.VIEWER,
            ),
        ),
    )
    return result, REFRESH_TOKEN, REFRESH_MAX_AGE


def test_login_returns_access_token_and_sets_refresh_cookie(client):
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.login",
        new=AsyncMock(return_value=login_result()),
    ) as login:
        response = client.post(
            "/auth/login",
            json={
                "email": "user@example.com",
                "password": "password123",
                "remember_me": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["access_token"] == "access-token"
    cookie = response.headers["set-cookie"]
    assert f"{settings.REFRESH_TOKEN_COOKIE_NAME}={REFRESH_TOKEN}" in cookie
    assert "HttpOnly" in cookie and "SameSite=none" in cookie
    assert f"Max-Age={REFRESH_MAX_AGE}" in cookie
    login.assert_awaited_once()


def test_login_raises_when_service_returns_no_data(client):
    service_result = (ApiResponse(data=None), REFRESH_TOKEN, REFRESH_MAX_AGE)
    with (
        patch(
            "app.api.v1.endpoints.auth_router.AuthService.login",
            new=AsyncMock(return_value=service_result),
        ),
        pytest.raises(InternalServerException, match="response data is missing"),
    ):
        client.post(
            "/auth/login",
            json={
                "email": "user@example.com",
                "password": "password123",
            },
        )


def test_refresh_rotates_refresh_cookie(client):
    result = ApiResponse(
        message="Token refreshed",
        data={
            "access_token": "new-access-token",
            "token_type": "bearer",
            "expires_in": 1800,
        },
    )
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.refresh_token",
        new=AsyncMock(return_value=(result, "new-refresh-token", REFRESH_MAX_AGE)),
    ) as refresh:
        response = client.post(
            "/auth/refresh",
            cookies={
                settings.REFRESH_TOKEN_COOKIE_NAME: REFRESH_TOKEN,
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["access_token"] == "new-access-token"
    assert "new-refresh-token" in response.headers["set-cookie"]
    refresh.assert_awaited_once_with(raw_refresh_token=REFRESH_TOKEN)


def test_logout_revokes_refresh_token_and_deletes_cookie(client):
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.logout_current_device",
        new=AsyncMock(),
    ) as logout:
        response = client.post(
            "/auth/logout",
            cookies={
                settings.REFRESH_TOKEN_COOKIE_NAME: REFRESH_TOKEN,
            },
        )

    assert response.status_code == 204
    assert f'{settings.REFRESH_TOKEN_COOKIE_NAME}=""' in response.headers["set-cookie"]
    logout.assert_awaited_once_with(REFRESH_TOKEN)


def test_logout_all_uses_authenticated_jwt_user(client):
    user = type("User", (), {"id": uuid4()})()

    async def current_user():
        return user

    client.app.dependency_overrides[get_current_user] = current_user
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.logout_all_devices",
        new=AsyncMock(),
    ) as logout_all:
        response = client.post("/auth/logout-all")

    assert response.status_code == 204
    logout_all.assert_awaited_once_with(user_id=user.id)


def test_request_passcode_uses_request_email_and_client_ip(client):
    with patch(
        "app.api.v1.endpoints.email_router.AuthService.request_passcode",
        new=AsyncMock(),
    ) as request_passcode:
        response = client.post(
            "/auth/passcode/request",
            json={
                "email": "user@example.com",
            },
        )

    assert response.status_code == 200
    assert request_passcode.await_args.kwargs["email"] == "user@example.com"
    assert request_passcode.await_args.kwargs["client_ip"] == "127.0.0.1"


def test_verify_passcode_returns_jwt_and_sets_refresh_cookie(client):
    with patch(
        "app.api.v1.endpoints.email_router.AuthService.verify_email_passcode",
        new=AsyncMock(return_value=login_result()),
    ):
        response = client.post(
            "/auth/passcode/verifications",
            json={
                "email": "user@example.com",
                "passcode": "123456",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["access_token"] == "access-token"
    assert REFRESH_TOKEN in response.headers["set-cookie"]


def test_oauth_start_redirects_to_provider(client):
    with patch(
        "app.api.v1.endpoints.oauth_router.AuthService.start_oauth",
        new=AsyncMock(return_value="https://provider.example/authorize"),
    ) as start_oauth:
        response = client.get("/auth/github", follow_redirects=False)

    assert response.status_code == 302
    start_oauth.assert_awaited_once_with(provider="github")


def test_oauth_callback_sets_refresh_cookie(client):
    with patch(
        "app.api.v1.endpoints.oauth_router.AuthService.oauth_callback",
        new=AsyncMock(return_value=login_result()),
    ) as callback:
        response = client.get(
            "/auth/github/callback?code=code&state=state",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert REFRESH_TOKEN in response.headers["set-cookie"]
    callback.assert_awaited_once_with(provider="github", code="code", state="state")


def test_oauth_callback_raises_when_response_data_is_missing(client):
    service_result = (ApiResponse(data=None), REFRESH_TOKEN, REFRESH_MAX_AGE)
    with (
        patch(
            "app.api.v1.endpoints.oauth_router.AuthService.oauth_callback",
            new=AsyncMock(return_value=service_result),
        ),
        pytest.raises(InternalServerException, match="session data is missing"),
    ):
        client.get("/auth/github/callback?code=code&state=state")

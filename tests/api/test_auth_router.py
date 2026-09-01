from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from tests.api.conftest import ApiClient

from app.api.v1.endpoints.auth_router import router
from app.db.redis import get_redis
from app.db.session import get_db
from app.exceptions.custom import InternalServerException, UnauthorizedException
from app.schemas.auth_schema import LoginResponse
from app.schemas.response import ApiResponse
from app.schemas.user_schema import UserResponse


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)

    async def dependency():
        return object()

    app.dependency_overrides[get_db] = dependency
    app.dependency_overrides[get_redis] = dependency
    return ApiClient(app)


def login_result(session_id):
    return ApiResponse[LoginResponse](
        message="Login successful",
        data=LoginResponse(
            session_id=session_id,
            user=UserResponse(
                id=uuid4(),
                email="user@example.com",
                first_name="Test",
                last_name="User",
                is_active=True,
            ),
        ),
    )


def test_login_sets_secure_session_cookie(client):
    session_id = uuid4()
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.login",
        new=AsyncMock(return_value=login_result(session_id)),
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
    assert response.json()["message"] == "Login successful"
    assert f"session={session_id}" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=none" in response.headers["set-cookie"]
    login.assert_awaited_once()


def test_login_without_remember_me_uses_standard_expiry(client):
    session_id = uuid4()
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.login",
        new=AsyncMock(return_value=login_result(session_id)),
    ):
        response = client.post(
            "/auth/login",
            json={
                "email": "user@example.com",
                "password": "password123",
                "remember_me": False,
            },
        )

    assert response.status_code == 200
    assert "Max-Age=" in response.headers["set-cookie"]


def test_login_raises_when_service_returns_no_data(client):
    with (
        patch(
            "app.api.v1.endpoints.auth_router.AuthService.login",
            new=AsyncMock(return_value=ApiResponse(data=None)),
        ),
        pytest.raises(InternalServerException, match="response data is missing"),
    ):
        client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )


def test_logout_revokes_valid_session_and_deletes_cookie(client):
    session_id = uuid4()
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.logout",
        new=AsyncMock(),
    ) as logout:
        response = client.post(
            "/auth/logout",
            cookies={"session": str(session_id)},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
    assert 'session=""' in response.headers["set-cookie"]
    logout.assert_awaited_once_with(session_id)


@pytest.mark.parametrize("cookies", [{}, {"session": "invalid-uuid"}])
def test_logout_ignores_missing_or_invalid_session(client, cookies):
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.logout",
        new=AsyncMock(),
    ) as logout:
        response = client.post("/auth/logout", cookies=cookies)

    assert response.status_code == 200
    logout.assert_not_awaited()


def test_session_returns_current_session(client):
    session_id = uuid4()
    expected = ApiResponse(message="Session active", data={"id": str(session_id)})
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.get_current_session",
        new=AsyncMock(return_value=expected),
    ) as get_current_session:
        response = client.get(
            "/auth/session",
            cookies={"session": str(session_id)},
        )

    assert response.status_code == 200
    assert response.json()["data"] == {"id": str(session_id)}
    get_current_session.assert_awaited_once_with(session_id)


@pytest.mark.parametrize(
    ("cookies", "message"),
    [
        ({}, "Session cookie is missing"),
        ({"session": "invalid-uuid"}, "Invalid session"),
    ],
)
def test_session_rejects_missing_or_invalid_cookie(client, cookies, message):
    with pytest.raises(UnauthorizedException, match=message):
        client.get("/auth/session", cookies=cookies)


def test_request_passcode_uses_request_email_and_client_ip(client):
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.request_passcode",
        new=AsyncMock(),
    ) as request_passcode:
        response = client.post(
            "/auth/passcode/request",
            json={"email": "user@example.com"},
        )

    assert response.status_code == 200
    assert response.json()["message"].startswith("Verification code sent")
    assert request_passcode.await_args.kwargs["email"] == "user@example.com"
    assert request_passcode.await_args.kwargs["client_ip"] == "127.0.0.1"


def test_verify_passcode_sets_session_cookie(client):
    session_id = uuid4()
    result = SimpleNamespace(
        data=SimpleNamespace(session_id=session_id),
        message="Login successful",
        success=True,
    )
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.verify_email_passcode",
        new=AsyncMock(return_value=result),
    ):
        response = client.post(
            "/auth/passcode/verify",
            json={"email": "user@example.com", "passcode": "123456"},
        )

    assert response.status_code == 200
    assert f"session={session_id}" in response.headers["set-cookie"]


def test_verify_passcode_raises_when_service_returns_no_data(client):
    with (
        patch(
            "app.api.v1.endpoints.auth_router.AuthService.verify_email_passcode",
            new=AsyncMock(return_value=ApiResponse(data=None)),
        ),
        pytest.raises(InternalServerException, match="response data is missing"),
    ):
        client.post(
            "/auth/passcode/verify",
            json={"email": "user@example.com", "passcode": "123456"},
        )


def test_oauth_start_redirects_to_provider(client):
    authorization_url = "https://provider.example/authorize"
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.start_oauth",
        new=AsyncMock(return_value=authorization_url),
    ) as start_oauth:
        response = client.get("/auth/github", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == authorization_url
    start_oauth.assert_awaited_once_with(provider="github")


def test_oauth_callback_redirects_and_sets_cookie(client):
    session_id = uuid4()
    result = SimpleNamespace(data={"session_id": session_id})
    with patch(
        "app.api.v1.endpoints.auth_router.AuthService.oauth_callback",
        new=AsyncMock(return_value=result),
    ) as callback:
        response = client.get(
            "/auth/github/callback?code=code&state=state",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert f"session={session_id}" in response.headers["set-cookie"]
    callback.assert_awaited_once_with(
        provider="github",
        code="code",
        state="state",
    )


def test_oauth_callback_raises_when_session_data_is_missing(client):
    with (
        patch(
            "app.api.v1.endpoints.auth_router.AuthService.oauth_callback",
            new=AsyncMock(return_value=ApiResponse(data=None)),
        ),
        pytest.raises(InternalServerException, match="session data is missing"),
    ):
        client.get("/auth/github/callback?code=code&state=state")

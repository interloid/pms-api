from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.core.settings import settings
from app.exceptions.custom import (
    ConflictException,
    NotFoundException,
    TooManyRequestsException,
    UnauthorizedException,
)
from app.models.refresh_token_model import Session
from app.models.user_identity_model import UserIdentity
from app.models.user_model import User
from app.services.auth_service import AuthService
from app.utils.helpers import utc_now


@pytest.fixture
def auth_service(db, redis):
    return AuthService(
        db=db,
        redis=redis,
    )


def build_service():
    db = MagicMock()

    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    redis = MagicMock(spec=Redis)
    redis.delete = AsyncMock()

    service = AuthService(
        db=db,
        redis=redis,
    )

    service.user_repo = MagicMock()
    service.user_identity_repo = MagicMock()
    service.session_repo = MagicMock()
    service.oauth_state_repo = MagicMock()

    # Async repository methods
    service.user_repo.get_by_email = AsyncMock()
    service.user_repo.get_by_id = AsyncMock()
    service.user_repo.create = AsyncMock()

    service.user_identity_repo.get_by_provider_identity = AsyncMock()
    service.user_identity_repo.create = AsyncMock()

    service.session_repo.create = AsyncMock()

    service.oauth_state_repo.create = AsyncMock()
    service.oauth_state_repo.consume = AsyncMock()

    return service, db


def build_active_user(
    *,
    user_id=None,
    email="john@example.com",
    first_name="John",
    last_name="Doe",
):
    return User(
        id=user_id or uuid4(),
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )


def build_inactive_user(
    *,
    user_id=None,
    email="john@example.com",
):
    return User(
        id=user_id or uuid4(),
        email=email,
        first_name="John",
        last_name="Doe",
        is_active=False,
    )


def build_session(*, user_id, session_id=None):
    return Session(
        id=session_id or uuid4(),
        user_id=user_id,
        expires_at=utc_now(),
    )


def build_oauth_client(
    *,
    userinfo: dict,
):

    client = MagicMock()

    client.fetch_token = AsyncMock()

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = userinfo
    response.raise_for_status = MagicMock()

    client.get = AsyncMock(
        return_value=response,
    )

    return client


@pytest.mark.asyncio
async def test_verify_email_passcode_creates_new_user(monkeypatch):
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    redis = MagicMock(spec=Redis)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    redis.set = AsyncMock()

    service = AuthService(
        db=db,
        redis=redis,
    )

    service.user_repo = MagicMock()
    service.user_identity_repo = MagicMock()
    service.session_repo = MagicMock()
    service.oauth_state_repo = MagicMock()

    service.user_repo.get_by_email = AsyncMock(
        return_value=None,
    )

    service.user_repo.create = AsyncMock()

    service.session_repo.create = AsyncMock()

    user_id = uuid4()
    session_id = uuid4()

    async def create_user(user):
        user.id = user_id
        return user

    async def create_session(session):
        session.id = session_id
        return session

    service.user_repo.create.side_effect = create_user
    service.session_repo.create.side_effect = create_session

    monkeypatch.setattr(
        "app.services.auth_service.get_passcode_attempts",
        AsyncMock(return_value=0),
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_passcode",
        AsyncMock(return_value="hashed-passcode"),
    )

    monkeypatch.setattr(
        "app.services.auth_service.verify_passcode",
        MagicMock(return_value=True),
    )

    monkeypatch.setattr(
        "app.services.auth_service.delete_passcode",
        AsyncMock(),
    )

    response = await service.verify_email_passcode(
        email="new@example.com",
        passcode="123456",
        redis=redis,
    )

    assert response.message == "Login successful"

    assert response.data.session_id == session_id

    assert response.data.user.id == user_id
    assert response.data.user.email == "new@example.com"
    assert response.data.user.first_name == "User"
    assert response.data.user.last_name == ""
    assert response.data.user.is_active is True

    service.user_repo.create.assert_awaited_once()
    service.session_repo.create.assert_awaited_once()

    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_email_passcode_rejects_inactive_user(monkeypatch):
    service, db = build_service()

    user = build_inactive_user()

    service.user_repo.get_by_email.return_value = user

    response_get_attempts = AsyncMock(return_value=0)

    monkeypatch.setattr(
        "app.services.auth_service.get_passcode_attempts",
        response_get_attempts,
    )

    with pytest.raises(
        UnauthorizedException,
        match="Invalid or expired passcode.",
    ):
        await service.verify_email_passcode(
            email=user.email,
            passcode="123456",
            redis=MagicMock(),
        )

    db.rollback.assert_awaited_once()

    service.user_repo.get_by_email.assert_awaited_once_with(
        user.email,
    )


@pytest.mark.asyncio
async def test_verify_email_passcode_rejects_too_many_attempts(
    monkeypatch,
):
    service, db = build_service()

    user = build_active_user()

    service.user_repo.get_by_email.return_value = user

    monkeypatch.setattr(
        "app.services.auth_service.get_passcode_attempts",
        AsyncMock(return_value=5),
    )
    monkeypatch.setattr(
        "app.services.auth_service.get_passcode_attempt_ttl",
        AsyncMock(return_value=240),
    )

    with pytest.raises(
        TooManyRequestsException,
        match="Too many attempts. Request a new passcode.",
    ) as exc_info:
        await service.verify_email_passcode(
            email=user.email,
            passcode="123456",
            redis=MagicMock(),
        )

    assert exc_info.value.details == {
        "attempts_used": 5,
        "max_attempts": settings.PASSCODE_MAX_ATTEMPTS,
        "remaining_attempts": 0,
        "retry_after_seconds": 240,
    }
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_email_passcode_rejects_missing_passcode(
    monkeypatch,
):
    service, db = build_service()

    user = build_active_user()

    service.user_repo.get_by_email.return_value = user

    monkeypatch.setattr(
        "app.services.auth_service.get_passcode_attempts",
        AsyncMock(return_value=0),
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_passcode",
        AsyncMock(return_value=None),
    )

    with pytest.raises(
        UnauthorizedException,
        match="Invalid or expired passcode.",
    ):
        await service.verify_email_passcode(
            email=user.email,
            passcode="123456",
            redis=MagicMock(),
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_email_passcode_rejects_invalid_passcode(
    monkeypatch,
):
    service, db = build_service()

    user = build_active_user()

    service.user_repo.get_by_email.return_value = user

    get_attempts = AsyncMock(return_value=0)
    increment_attempts = AsyncMock(return_value=1)

    monkeypatch.setattr(
        "app.services.auth_service.get_passcode_attempts",
        get_attempts,
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_passcode",
        AsyncMock(return_value="hashed-passcode"),
    )

    monkeypatch.setattr(
        "app.services.auth_service.verify_passcode",
        MagicMock(return_value=False),
    )

    monkeypatch.setattr(
        "app.services.auth_service.increment_passcode_attempts",
        increment_attempts,
    )
    monkeypatch.setattr(
        "app.services.auth_service.get_passcode_attempt_ttl",
        AsyncMock(return_value=299),
    )

    with pytest.raises(
        UnauthorizedException,
        match="Invalid or expired passcode.",
    ) as exc_info:
        await service.verify_email_passcode(
            email=user.email,
            passcode="wrong",
            redis=MagicMock(),
        )

    assert exc_info.value.details == {
        "attempts_used": 1,
        "max_attempts": settings.PASSCODE_MAX_ATTEMPTS,
        "remaining_attempts": 2,
        "retry_after_seconds": 299,
    }
    increment_attempts.assert_awaited_once()

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_email_passcode_rolls_back_on_unexpected_error(
    monkeypatch,
):
    service, db = build_service()

    service.user_repo.get_by_email.side_effect = RuntimeError(
        "database error",
    )

    with pytest.raises(RuntimeError, match="database error"):
        await service.verify_email_passcode(
            email="john@example.com",
            passcode="123456",
            redis=MagicMock(),
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_oauth_google_success(monkeypatch):
    service, db = build_service()

    state = "test-google-state"

    monkeypatch.setattr(
        "app.services.auth_service.generate_oauth_state",
        MagicMock(return_value=state),
    )

    url = await service.start_oauth("google")

    assert "client_id=" in url
    assert "redirect_uri=" in url
    assert "response_type=code" in url
    assert "scope=" in url
    assert f"state={state}" in url

    service.oauth_state_repo.create.assert_awaited_once()

    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_oauth_unsupported_provider():
    service, db = build_service()

    with pytest.raises(
        NotFoundException,
        match="OAuth provider not supported",
    ):
        await service.start_oauth("facebook")

    service.oauth_state_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_oauth_state_success():
    service, db = build_service()

    service.oauth_state_repo.consume.return_value = "google"

    await service.validate_oauth_state(
        provider="google",
        state="valid-state",
    )

    service.oauth_state_repo.consume.assert_awaited_once_with(
        "valid-state",
    )


@pytest.mark.asyncio
async def test_validate_oauth_state_rejects_missing_state():
    service, db = build_service()

    service.oauth_state_repo.consume.return_value = None

    with pytest.raises(
        UnauthorizedException,
        match="Invalid or expired OAuth state",
    ):
        await service.validate_oauth_state(
            provider="google",
            state="expired-state",
        )


@pytest.mark.asyncio
async def test_validate_oauth_state_rejects_provider_mismatch():
    service, db = build_service()

    service.oauth_state_repo.consume.return_value = "github"

    with pytest.raises(
        UnauthorizedException,
        match="Invalid OAuth state",
    ):
        await service.validate_oauth_state(
            provider="google",
            state="github-state",
        )


@pytest.mark.asyncio
async def test_oauth_callback_google_rejects_unverified_email(
    monkeypatch,
):
    service, db = build_service()

    service.oauth_state_repo.consume.return_value = "google"

    client = build_oauth_client(
        userinfo={
            "sub": "google-123",
            "email": "john@gmail.com",
            "email_verified": False,
        },
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        MagicMock(return_value=client),
    )

    with pytest.raises(
        UnauthorizedException,
        match="Google email is not verified",
    ):
        await service.oauth_callback(
            provider="google",
            code="code",
            state="state",
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_oauth_callback_google_rejects_missing_email(
    monkeypatch,
):
    service, db = build_service()

    service.oauth_state_repo.consume.return_value = "google"

    client = build_oauth_client(
        userinfo={
            "sub": "google-123",
            "email_verified": True,
        },
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        MagicMock(return_value=client),
    )

    with pytest.raises(
        UnauthorizedException,
        match="Google account does not provide an email",
    ):
        await service.oauth_callback(
            provider="google",
            code="code",
            state="state",
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_github_email_returns_primary_verified_email():
    service, db = build_service()

    client = MagicMock()

    response = MagicMock()

    response.json.return_value = [
        {
            "email": "secondary@example.com",
            "primary": False,
            "verified": True,
        },
        {
            "email": "primary@example.com",
            "primary": True,
            "verified": True,
        },
    ]

    response.raise_for_status = MagicMock()

    client.get = AsyncMock(
        return_value=response,
    )

    email = await service.get_github_email(client)

    assert email == "primary@example.com"

    client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_github_email_returns_verified_email_when_no_primary():
    service, db = build_service()

    client = MagicMock()

    response = MagicMock()

    response.json.return_value = [
        {
            "email": "unverified@example.com",
            "primary": True,
            "verified": False,
        },
        {
            "email": "verified@example.com",
            "primary": False,
            "verified": True,
        },
    ]

    response.raise_for_status = MagicMock()

    client.get = AsyncMock(
        return_value=response,
    )

    email = await service.get_github_email(client)

    assert email == "verified@example.com"


@pytest.mark.asyncio
async def test_get_github_email_rejects_when_no_verified_email():
    service, db = build_service()

    client = MagicMock()

    response = MagicMock()

    response.json.return_value = [
        {
            "email": "unverified@example.com",
            "primary": True,
            "verified": False,
        },
    ]

    response.raise_for_status = MagicMock()

    client.get = AsyncMock(
        return_value=response,
    )

    with pytest.raises(
        UnauthorizedException,
        match="No verified email found for GitHub account",
    ):
        await service.get_github_email(client)


@pytest.mark.asyncio
async def test_oauth_callback_microsoft_rejects_missing_email(
    monkeypatch,
):
    service, db = build_service()

    service.oauth_state_repo.consume.return_value = "microsoft"

    client = build_oauth_client(
        userinfo={
            "sub": "microsoft-123",
            "name": "John Doe",
        },
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        MagicMock(return_value=client),
    )

    with pytest.raises(
        UnauthorizedException,
        match="Microsoft account does not provide an email",
    ):
        await service.oauth_callback(
            provider="microsoft",
            code="code",
            state="state",
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_oauth_callback_rejects_existing_email_without_identity(
    monkeypatch,
):
    service, db = build_service()

    service.oauth_state_repo.consume.return_value = "google"

    service.user_identity_repo.get_by_provider_identity.return_value = None

    existing_user = build_active_user(
        email="existing@gmail.com",
    )

    service.user_repo.get_by_email.return_value = existing_user

    client = build_oauth_client(
        userinfo={
            "sub": "google-123",
            "email": "existing@gmail.com",
            "email_verified": True,
            "given_name": "John",
            "family_name": "Doe",
        },
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        MagicMock(return_value=client),
    )

    with pytest.raises(
        ConflictException,
        match="An account with this email already exists",
    ):
        await service.oauth_callback(
            provider="google",
            code="code",
            state="state",
        )

    db.rollback.assert_awaited_once()

    service.user_repo.create.assert_not_awaited()
    service.user_identity_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_oauth_callback_rejects_inactive_user(
    monkeypatch,
):
    service, db = build_service()

    user_id = uuid4()

    inactive_user = build_inactive_user(
        user_id=user_id,
        email="inactive@gmail.com",
    )

    identity = UserIdentity(
        id=uuid4(),
        user_id=user_id,
        provider="google",
        provider_user_id="google-123",
        email="inactive@gmail.com",
    )

    service.oauth_state_repo.consume.return_value = "google"

    service.user_identity_repo.get_by_provider_identity.return_value = identity

    service.user_repo.get_by_id.return_value = inactive_user

    client = build_oauth_client(
        userinfo={
            "sub": "google-123",
            "email": "inactive@gmail.com",
            "email_verified": True,
            "given_name": "John",
            "family_name": "Doe",
        },
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        MagicMock(return_value=client),
    )

    with pytest.raises(
        UnauthorizedException,
        match="User account is inactive",
    ):
        await service.oauth_callback(
            provider="google",
            code="code",
            state="state",
        )

    db.rollback.assert_awaited_once()

    service.session_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_oauth_callback_identity_user_not_found(
    monkeypatch,
):
    service, db = build_service()

    user_id = uuid4()

    identity = UserIdentity(
        id=uuid4(),
        user_id=user_id,
        provider="google",
        provider_user_id="google-123",
        email="john@gmail.com",
    )

    service.oauth_state_repo.consume.return_value = "google"

    service.user_identity_repo.get_by_provider_identity.return_value = identity

    service.user_repo.get_by_id.return_value = None

    client = build_oauth_client(
        userinfo={
            "sub": "google-123",
            "email": "john@gmail.com",
            "email_verified": True,
            "given_name": "John",
            "family_name": "Doe",
        },
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        MagicMock(return_value=client),
    )

    with pytest.raises(
        NotFoundException,
        match="User associated with OAuth identity not found",
    ):
        await service.oauth_callback(
            provider="google",
            code="code",
            state="state",
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_oauth_callback_rejects_invalid_state(
    monkeypatch,
):
    service, db = build_service()

    service.oauth_state_repo.consume.return_value = None

    with pytest.raises(
        UnauthorizedException,
        match="Invalid or expired OAuth state",
    ):
        await service.oauth_callback(
            provider="google",
            code="code",
            state="invalid-state",
        )

    db.rollback.assert_awaited_once()

    service.user_repo.get_by_email.assert_not_awaited()
    service.session_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_oauth_callback_rejects_provider_state_mismatch(
    monkeypatch,
):
    service, db = build_service()

    service.oauth_state_repo.consume.return_value = "github"

    with pytest.raises(
        UnauthorizedException,
        match="Invalid OAuth state",
    ):
        await service.oauth_callback(
            provider="google",
            code="code",
            state="github-state",
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_oauth_callback_rolls_back_on_unexpected_error(
    monkeypatch,
):
    service, db = build_service()

    service.oauth_state_repo.consume.side_effect = RuntimeError(
        "Redis unavailable",
    )

    with pytest.raises(
        RuntimeError,
        match="Redis unavailable",
    ):
        await service.oauth_callback(
            provider="google",
            code="code",
            state="state",
        )

    db.rollback.assert_awaited_once()

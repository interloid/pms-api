from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_refresh_token
from app.core.settings import settings
from app.exceptions.custom import (
    ConflictException,
    UnauthorizedException,
)
from app.main import app
from app.models.refresh_token_model import RefreshToken
from app.models.user_identity_model import UserIdentity
from app.models.user_model import User
from app.services.auth_service import AuthService


@pytest.fixture
def oauth_service(
    client: AsyncClient,
    db_session: AsyncSession,
) -> AuthService:
    # The client fixture starts the FastAPI lifespan,
    # which creates app.state.redis.
    _ = client

    return AuthService(
        db=db_session,
        redis=app.state.redis,
    )


def build_google_client(
    userinfo: dict,
) -> MagicMock:
    oauth_client = MagicMock()

    oauth_client.fetch_token = AsyncMock(
        return_value={
            "access_token": "provider-access-token",
        }
    )

    userinfo_response = MagicMock()
    userinfo_response.status_code = 200
    userinfo_response.json.return_value = userinfo
    userinfo_response.raise_for_status = MagicMock()

    oauth_client.get = AsyncMock(
        return_value=userinfo_response,
    )
    oauth_client.__aenter__ = AsyncMock(return_value=oauth_client)
    oauth_client.__aexit__ = AsyncMock(return_value=None)

    return oauth_client


async def create_oauth_state(
    *,
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
    provider: str = "google",
) -> str:
    state = f"oauth-state-{uuid4()}"

    monkeypatch.setattr(
        "app.services.auth_service.generate_oauth_state",
        lambda: state,
    )

    await oauth_service.start_oauth(
        provider=provider,
    )

    return state


@pytest.mark.asyncio
async def test_google_oauth_creates_new_user_and_tokens(
    client: AsyncClient,
    db_session: AsyncSession,
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = f"oauth-{uuid4()}@example.com"

    state = await create_oauth_state(
        oauth_service=oauth_service,
        monkeypatch=monkeypatch,
    )

    provider_client = build_google_client(
        {
            "sub": f"google-{uuid4()}",
            "email": email,
            "email_verified": True,
            "given_name": "OAuth",
            "family_name": "User",
        }
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        lambda provider: provider_client,
    )

    (
        result,
        raw_refresh_token,
        refresh_max_age,
    ) = await oauth_service.oauth_callback(
        provider="google",
        code="valid-code",
        state=state,
    )

    assert result.message == "Google authentication successful"
    assert result.data is not None
    assert result.data.access_token
    assert result.data.token_type == "bearer"

    assert raw_refresh_token
    assert refresh_max_age == (settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)

    provider_client.fetch_token.assert_awaited_once()
    provider_client.get.assert_awaited_once()

    user_result = await db_session.execute(
        select(User).where(
            User.email == email,
        )
    )
    stored_user = user_result.scalar_one()

    assert stored_user.first_name == "OAuth"
    assert stored_user.last_name == "User"
    assert stored_user.is_active is True

    identity_result = await db_session.execute(
        select(UserIdentity).where(
            UserIdentity.user_id == stored_user.id,
            UserIdentity.provider == "google",
        )
    )
    stored_identity = identity_result.scalar_one()

    assert stored_identity.email == email
    assert stored_identity.provider_user_id.startswith("google-")

    refresh_result = await db_session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == stored_user.id,
        )
    )
    stored_refresh_token = refresh_result.scalar_one()

    assert stored_refresh_token.is_revoked is False
    assert stored_refresh_token.token_hash != raw_refresh_token
    assert stored_refresh_token.token_hash == hash_refresh_token(raw_refresh_token)

    headers = {"Authorization": (f"Bearer {result.data.access_token}")}

    me_response = await client.get(
        "/api/v1/auth/me",
        headers=headers,
    )

    assert me_response.status_code == 200
    assert me_response.json()["data"]["email"] == email


@pytest.mark.asyncio
async def test_google_oauth_existing_identity_logs_in_without_duplicate(
    db_session: AsyncSession,
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = f"existing-oauth-{uuid4()}@example.com"
    provider_user_id = f"google-{uuid4()}"

    user = User(
        email=email,
        first_name="Existing",
        last_name="User",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    user_id = user.id

    identity = UserIdentity(
        user_id=user_id,
        provider="google",
        provider_user_id=provider_user_id,
        email=email,
    )
    db_session.add(identity)
    await db_session.commit()

    state = await create_oauth_state(
        oauth_service=oauth_service,
        monkeypatch=monkeypatch,
    )

    provider_client = build_google_client(
        {
            "sub": provider_user_id,
            "email": email,
            "email_verified": True,
            "given_name": "Different",
            "family_name": "Name",
        }
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        lambda provider: provider_client,
    )

    result, raw_refresh_token, _ = await oauth_service.oauth_callback(
        provider="google",
        code="valid-code",
        state=state,
    )

    assert result.data is not None
    assert result.data.access_token
    assert raw_refresh_token

    user_count_result = await db_session.execute(
        select(func.count()).select_from(User).where(User.email == email)
    )

    assert user_count_result.scalar_one() == 1

    identity_count_result = await db_session.execute(
        select(func.count())
        .select_from(UserIdentity)
        .where(
            UserIdentity.provider == "google",
            UserIdentity.provider_user_id == provider_user_id,
        )
    )

    assert identity_count_result.scalar_one() == 1


@pytest.mark.asyncio
async def test_google_oauth_rejects_existing_email_without_identity(
    db_session: AsyncSession,
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = f"password-user-{uuid4()}@example.com"

    existing_user = User(
        email=email,
        first_name="Password",
        last_name="User",
        is_active=True,
    )
    db_session.add(existing_user)
    await db_session.commit()

    state = await create_oauth_state(
        oauth_service=oauth_service,
        monkeypatch=monkeypatch,
    )

    provider_client = build_google_client(
        {
            "sub": f"google-{uuid4()}",
            "email": email,
            "email_verified": True,
            "given_name": "OAuth",
            "family_name": "User",
        }
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        lambda provider: provider_client,
    )

    with pytest.raises(
        ConflictException,
        match="An account with this email already exists",
    ):
        await oauth_service.oauth_callback(
            provider="google",
            code="valid-code",
            state=state,
        )


@pytest.mark.asyncio
async def test_google_oauth_rejects_inactive_user(
    db_session: AsyncSession,
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = f"inactive-oauth-{uuid4()}@example.com"
    provider_user_id = f"google-{uuid4()}"

    user = User(
        email=email,
        first_name="Inactive",
        last_name="User",
        is_active=False,
    )
    db_session.add(user)
    await db_session.flush()

    identity = UserIdentity(
        user_id=user.id,
        provider="google",
        provider_user_id=provider_user_id,
        email=email,
    )
    db_session.add(identity)
    await db_session.commit()

    state = await create_oauth_state(
        oauth_service=oauth_service,
        monkeypatch=monkeypatch,
    )

    provider_client = build_google_client(
        {
            "sub": provider_user_id,
            "email": email,
            "email_verified": True,
            "given_name": "Inactive",
            "family_name": "User",
        }
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        lambda provider: provider_client,
    )

    with pytest.raises(
        UnauthorizedException,
        match="User account is inactive",
    ):
        await oauth_service.oauth_callback(
            provider="google",
            code="valid-code",
            state=state,
        )


@pytest.mark.asyncio
async def test_google_oauth_rejects_missing_email(
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = await create_oauth_state(
        oauth_service=oauth_service,
        monkeypatch=monkeypatch,
    )

    provider_client = build_google_client(
        {
            "sub": f"google-{uuid4()}",
            "email_verified": True,
        }
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        lambda provider: provider_client,
    )

    with pytest.raises(
        UnauthorizedException,
        match="Google account does not provide an email",
    ):
        await oauth_service.oauth_callback(
            provider="google",
            code="valid-code",
            state=state,
        )


@pytest.mark.asyncio
async def test_google_oauth_rejects_unverified_email(
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = await create_oauth_state(
        oauth_service=oauth_service,
        monkeypatch=monkeypatch,
    )

    provider_client = build_google_client(
        {
            "sub": f"google-{uuid4()}",
            "email": f"unverified-{uuid4()}@example.com",
            "email_verified": False,
        }
    )

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        lambda provider: provider_client,
    )

    with pytest.raises(
        UnauthorizedException,
        match="Google email is not verified",
    ):
        await oauth_service.oauth_callback(
            provider="google",
            code="valid-code",
            state=state,
        )


@pytest.mark.asyncio
async def test_oauth_callback_rejects_invalid_state_before_provider_call(
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_factory = MagicMock()

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        provider_factory,
    )

    with pytest.raises(
        UnauthorizedException,
        match="Invalid or expired OAuth state",
    ):
        await oauth_service.oauth_callback(
            provider="google",
            code="valid-code",
            state=f"missing-state-{uuid4()}",
        )

    provider_factory.assert_not_called()


@pytest.mark.asyncio
async def test_oauth_callback_propagates_provider_failure(
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = await create_oauth_state(
        oauth_service=oauth_service,
        monkeypatch=monkeypatch,
    )

    provider_client = MagicMock()
    provider_client.fetch_token = AsyncMock(
        side_effect=RuntimeError(
            "OAuth provider unavailable",
        )
    )
    provider_client.__aenter__ = AsyncMock(return_value=provider_client)
    provider_client.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "app.services.auth_service.get_oauth_client",
        lambda provider: provider_client,
    )

    with pytest.raises(
        RuntimeError,
        match="OAuth provider unavailable",
    ):
        await oauth_service.oauth_callback(
            provider="google",
            code="invalid-code",
            state=state,
        )

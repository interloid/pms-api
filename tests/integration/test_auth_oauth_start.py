from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import (
    NotFoundException,
    UnauthorizedException,
)
from app.main import app
from app.services.auth_service import AuthService


@pytest.fixture
def oauth_service(
    client: AsyncClient,
    db_session: AsyncSession,
) -> AuthService:

    return AuthService(
        db=db_session,
        redis=app.state.redis,
    )


@pytest.mark.asyncio
async def test_start_google_oauth_creates_valid_state(
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = f"oauth-state-{uuid4()}"

    monkeypatch.setattr(
        "app.services.auth_service.generate_oauth_state",
        lambda: state,
    )

    authorization_url = await oauth_service.start_oauth(
        provider="google",
    )

    parsed_url = urlparse(authorization_url)
    query = parse_qs(parsed_url.query)

    assert query["state"] == [state]
    assert query["response_type"] == ["code"]
    assert "client_id" in query
    assert "redirect_uri" in query
    assert "scope" in query

    # This proves that start_oauth stored the state in Redis.
    await oauth_service.validate_oauth_state(
        provider="google",
        state=state,
    )


@pytest.mark.asyncio
async def test_oauth_state_can_only_be_used_once(
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = f"oauth-state-{uuid4()}"

    monkeypatch.setattr(
        "app.services.auth_service.generate_oauth_state",
        lambda: state,
    )

    await oauth_service.start_oauth(
        provider="google",
    )

    # First validation consumes the Redis state.
    await oauth_service.validate_oauth_state(
        provider="google",
        state=state,
    )

    # The same state must not work again.
    with pytest.raises(
        UnauthorizedException,
        match="Invalid or expired OAuth state",
    ):
        await oauth_service.validate_oauth_state(
            provider="google",
            state=state,
        )


@pytest.mark.asyncio
async def test_validate_oauth_state_rejects_unknown_state(
    oauth_service: AuthService,
) -> None:
    unknown_state = f"missing-state-{uuid4()}"

    with pytest.raises(
        UnauthorizedException,
        match="Invalid or expired OAuth state",
    ):
        await oauth_service.validate_oauth_state(
            provider="google",
            state=unknown_state,
        )


@pytest.mark.asyncio
async def test_validate_oauth_state_rejects_provider_mismatch(
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = f"oauth-state-{uuid4()}"

    monkeypatch.setattr(
        "app.services.auth_service.generate_oauth_state",
        lambda: state,
    )

    await oauth_service.start_oauth(
        provider="google",
    )

    with pytest.raises(
        UnauthorizedException,
        match="Invalid OAuth state",
    ):
        await oauth_service.validate_oauth_state(
            provider="github",
            state=state,
        )


@pytest.mark.asyncio
async def test_provider_mismatch_still_consumes_state(
    oauth_service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = f"oauth-state-{uuid4()}"

    monkeypatch.setattr(
        "app.services.auth_service.generate_oauth_state",
        lambda: state,
    )

    await oauth_service.start_oauth(
        provider="google",
    )

    with pytest.raises(UnauthorizedException):
        await oauth_service.validate_oauth_state(
            provider="github",
            state=state,
        )

    with pytest.raises(
        UnauthorizedException,
        match="Invalid or expired OAuth state",
    ):
        await oauth_service.validate_oauth_state(
            provider="google",
            state=state,
        )


@pytest.mark.asyncio
async def test_start_oauth_rejects_unsupported_provider(
    oauth_service: AuthService,
) -> None:
    with pytest.raises(
        NotFoundException,
        match="OAuth provider not supported",
    ):
        await oauth_service.start_oauth(
            provider="facebook",
        )

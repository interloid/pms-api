from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.exceptions.custom import (
    ConflictException,
    UnauthorizedException,
)
from app.models.session_model import Session
from app.services.auth_service import AuthService


def make_user(
    *,
    user_id=None,
    email="user@example.com",
    hashed_password="hashed-password",
    first_name="John",
    last_name="Doe",
    is_active=True,
):
    user = MagicMock()

    user.id = user_id or uuid4()
    user.email = email
    user.hashed_password = hashed_password
    user.first_name = first_name
    user.last_name = last_name
    user.is_active = is_active

    return user


def make_login_data(
    *,
    email="user@example.com",
    password="password123",
    remember_me=False,
):
    login_data = MagicMock()

    login_data.email = email
    login_data.password = password
    login_data.remember_me = remember_me

    return login_data


@pytest.mark.asyncio
async def test_rollback_calls_db_rollback():
    db = MagicMock()
    db.rollback = AsyncMock()

    service = AuthService(db)

    await service._rollback()

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_returns_successful_login_response():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    service = AuthService(db)

    user = make_user()

    login_data = make_login_data(
        email=user.email,
        password="password123",
        remember_me=True,
    )

    session_id = uuid4()

    session = MagicMock(spec=Session)
    session.id = session_id

    service.user_repo.get_by_email = AsyncMock(
        return_value=user,
    )

    service.session_repo.create = AsyncMock()

    with patch(
        "app.services.auth_service.verify_password",
        return_value=True,
    ), patch(
        "app.services.auth_service.Session",
        return_value=session,
    ):

        result = await service.login(login_data)

    assert result.message == "Login successful"

    assert result.data.session_id == session_id

    assert result.data.user.id == user.id
    assert result.data.user.email == user.email
    assert result.data.user.first_name == user.first_name
    assert result.data.user.last_name == user.last_name
    assert result.data.user.is_active is True

    service.user_repo.get_by_email.assert_awaited_once_with(
        user.email,
    )

    service.session_repo.create.assert_awaited_once_with(
        session,
    )

    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_creates_session_with_remember_me_false():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    service = AuthService(db)

    user = make_user()

    login_data = make_login_data(
        email=user.email,
        password="password123",
        remember_me=False,
    )

    session = MagicMock(spec=Session)
    session.id = uuid4()

    service.user_repo.get_by_email = AsyncMock(
        return_value=user,
    )

    service.session_repo.create = AsyncMock()

    with patch(
        "app.services.auth_service.verify_password",
        return_value=True,
    ), patch(
        "app.services.auth_service.Session",
        return_value=session,
    ):

        await service.login(login_data)

    service.session_repo.create.assert_awaited_once_with(
        session,
    )


@pytest.mark.asyncio
async def test_login_raises_unauthorized_when_user_does_not_exist():
    db = MagicMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    service = AuthService(db)

    login_data = make_login_data()

    service.user_repo.get_by_email = AsyncMock(
        return_value=None,
    )

    with pytest.raises(
        UnauthorizedException,
        match="Invalid email or password",
    ):
        await service.login(login_data)

    service.user_repo.get_by_email.assert_awaited_once_with(
        login_data.email,
    )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

    service.session_repo.create = AsyncMock()
    service.session_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_raises_unauthorized_when_user_has_no_password():
    db = MagicMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    service = AuthService(db)

    user = make_user(
        hashed_password=None,
    )

    login_data = make_login_data(
        email=user.email,
    )

    service.user_repo.get_by_email = AsyncMock(
        return_value=user,
    )

    with pytest.raises(
        UnauthorizedException,
        match="Invalid email or password",
    ):
        await service.login(login_data)

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

    service.session_repo.create = AsyncMock()
    service.session_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_raises_unauthorized_when_password_is_invalid():
    db = MagicMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    service = AuthService(db)

    user = make_user()

    login_data = make_login_data(
        email=user.email,
        password="wrong-password",
    )

    service.user_repo.get_by_email = AsyncMock(
        return_value=user,
    )

    with patch(
        "app.services.auth_service.verify_password",
        return_value=False,
    ) as mock_verify:

        with pytest.raises(
            UnauthorizedException,
            match="Invalid email or password",
        ):
            await service.login(login_data)

    mock_verify.assert_called_once_with(
        login_data.password,
        user.hashed_password,
    )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    service.session_repo.create = AsyncMock()
    service.session_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_raises_unauthorized_when_user_is_inactive():
    db = MagicMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    service = AuthService(db)

    user = make_user(
        is_active=False,
    )

    login_data = make_login_data(
        email=user.email,
    )

    service.user_repo.get_by_email = AsyncMock(
        return_value=user,
    )

    with patch(
        "app.services.auth_service.verify_password",
        return_value=True,
    ) as mock_verify:

        with pytest.raises(
            UnauthorizedException,
            match="Invalid email or password",
        ):
            await service.login(login_data)

    mock_verify.assert_called_once_with(
        login_data.password,
        user.hashed_password,
    )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    
    service.session_repo.create = AsyncMock()
    service.session_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_rolls_back_when_get_user_raises_exception():
    db = MagicMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    service = AuthService(db)

    login_data = make_login_data()

    error = RuntimeError("Database error")

    service.user_repo.get_by_email = AsyncMock(
        side_effect=error,
    )

    with patch(
        "app.services.auth_service.logger.exception",
    ) as mock_logger:

        with pytest.raises(
            RuntimeError,
            match="Database error",
        ):
            await service.login(login_data)

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

    mock_logger.assert_called_once_with(
        "Unexpected error",
    )


@pytest.mark.asyncio
async def test_login_rolls_back_when_session_creation_fails():
    db = MagicMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    service = AuthService(db)

    user = make_user()

    login_data = make_login_data(
        email=user.email,
    )

    service.user_repo.get_by_email = AsyncMock(
        return_value=user,
    )

    service.session_repo.create = AsyncMock(
        side_effect=RuntimeError("Session creation failed"),
    )

    with patch(
        "app.services.auth_service.verify_password",
        return_value=True,
    ), patch(
        "app.services.auth_service.logger.exception",
    ) as mock_logger:

        with pytest.raises(
            RuntimeError,
            match="Session creation failed",
        ):
            await service.login(login_data)

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

    mock_logger.assert_called_once_with(
        "Unexpected error",
    )


@pytest.mark.asyncio
async def test_login_rolls_back_when_commit_fails():
    db = MagicMock()

    db.commit = AsyncMock(
        side_effect=RuntimeError("Commit failed"),
    )

    db.rollback = AsyncMock()

    service = AuthService(db)

    user = make_user()

    login_data = make_login_data(
        email=user.email,
    )

    session = MagicMock(spec=Session)
    session.id = uuid4()

    service.user_repo.get_by_email = AsyncMock(
        return_value=user,
    )

    service.session_repo.create = AsyncMock()

    with patch(
        "app.services.auth_service.verify_password",
        return_value=True,
    ), patch(
        "app.services.auth_service.Session",
        return_value=session,
    ), patch(
        "app.services.auth_service.logger.exception",
    ):

        with pytest.raises(
            RuntimeError,
            match="Commit failed",
        ):
            await service.login(login_data)

    db.commit.assert_awaited_once()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_rolls_back_when_session_repo_raises_app_exception():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    service = AuthService(db)

    user = make_user()

    login_data = make_login_data(
        email=user.email,
    )

    service.user_repo.get_by_email = AsyncMock(
        return_value=user,
    )

    service.session_repo.create = AsyncMock(
        side_effect=ConflictException(
            message="Session conflict",
        ),
    )

    with patch(
        "app.services.auth_service.verify_password",
        return_value=True,
    ):

        with pytest.raises(
            ConflictException,
            match="Session conflict",
        ):
            await service.login(login_data)

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_deletes_existing_session():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    service = AuthService(db)

    session_id = uuid4()

    session = MagicMock(spec=Session)
    session.id = session_id

    service.session_repo.get_by_id = AsyncMock(
        return_value=session,
    )

    service.session_repo.delete = AsyncMock()

    result = await service.logout(
        session_id=session_id,
    )

    assert result.message == "Logged out successfully"

    service.session_repo.get_by_id.assert_awaited_once_with(
        session_id,
    )

    service.session_repo.delete.assert_awaited_once_with(
        session,
    )

    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_returns_success_when_session_does_not_exist():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    service = AuthService(db)

    session_id = uuid4()

    service.session_repo.get_by_id = AsyncMock(
        return_value=None,
    )

    service.session_repo.delete = AsyncMock()

    result = await service.logout(
        session_id=session_id,
    )

    assert result.message == "Logged out successfully"

    service.session_repo.get_by_id.assert_awaited_once_with(
        session_id,
    )

    service.session_repo.delete.assert_not_awaited()

    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_rolls_back_when_get_session_fails():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    service = AuthService(db)

    session_id = uuid4()

    service.session_repo.get_by_id = AsyncMock(
        side_effect=RuntimeError("Database error"),
    )

    with patch(
        "app.services.auth_service.logger.exception",
    ) as mock_logger:

        with pytest.raises(
            RuntimeError,
            match="Database error",
        ):
            await service.logout(
                session_id=session_id,
            )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

    mock_logger.assert_called_once_with(
        "Unexpected error while refreshing token",
    )


@pytest.mark.asyncio
async def test_logout_rolls_back_when_delete_fails():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    service = AuthService(db)

    session_id = uuid4()

    session = MagicMock(spec=Session)
    session.id = session_id

    service.session_repo.get_by_id = AsyncMock(
        return_value=session,
    )

    service.session_repo.delete = AsyncMock(
        side_effect=RuntimeError("Delete failed"),
    )

    with patch(
        "app.services.auth_service.logger.exception",
    ) as mock_logger:

        with pytest.raises(
            RuntimeError,
            match="Delete failed",
        ):
            await service.logout(
                session_id=session_id,
            )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()

    mock_logger.assert_called_once_with(
        "Unexpected error while refreshing token",
    )


@pytest.mark.asyncio
async def test_logout_rolls_back_when_commit_fails():
    db = MagicMock()

    db.commit = AsyncMock(
        side_effect=RuntimeError("Commit failed"),
    )

    db.rollback = AsyncMock()

    service = AuthService(db)

    session_id = uuid4()

    session = MagicMock(spec=Session)
    session.id = session_id

    service.session_repo.get_by_id = AsyncMock(
        return_value=session,
    )

    service.session_repo.delete = AsyncMock()

    with patch(
        "app.services.auth_service.logger.exception",
    ):

        with pytest.raises(
            RuntimeError,
            match="Commit failed",
        ):
            await service.logout(
                session_id=session_id,
            )

    db.commit.assert_awaited_once()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_rolls_back_when_delete_raises_app_exception():
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    service = AuthService(db)

    session_id = uuid4()

    session = MagicMock(spec=Session)
    session.id = session_id

    service.session_repo.get_by_id = AsyncMock(
        return_value=session,
    )

    service.session_repo.delete = AsyncMock(
        side_effect=ConflictException(
            message="Unable to delete session",
        ),
    )

    with pytest.raises(
        ConflictException,
        match="Unable to delete session",
    ):
        await service.logout(
            session_id=session_id,
        )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    
    
    
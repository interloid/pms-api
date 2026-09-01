from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import get_current_user, get_product_image_service
from app.core.security import create_access_token
from app.exceptions.custom import UnauthorizedException


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_bearer_token():
    with pytest.raises(UnauthorizedException, match="Authentication required"):
        await get_current_user(credentials=None, db=object())


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_access_token():
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid-token",
    )
    with pytest.raises(UnauthorizedException, match="Invalid access token"):
        await get_current_user(credentials=credentials, db=object())


@pytest.mark.asyncio
async def test_get_current_user_rejects_non_bearer_scheme():
    credentials = HTTPAuthorizationCredentials(scheme="Basic", credentials="token")
    with pytest.raises(UnauthorizedException, match="Invalid authentication scheme"):
        await get_current_user(credentials=credentials, db=object())


@pytest.mark.asyncio
async def test_get_current_user_returns_active_user_from_access_token():
    user_id = uuid4()
    expected_user = MagicMock(id=user_id, is_active=True)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token({"sub": str(user_id)}),
    )
    with patch(
        "app.api.dependencies.UserRepository.get_by_id",
        new=AsyncMock(return_value=expected_user),
    ) as get_by_id:
        result = await get_current_user(credentials=credentials, db=object())

    assert result is expected_user
    get_by_id.assert_awaited_once_with(user_id)


@pytest.mark.asyncio
async def test_get_current_user_rejects_inactive_user():
    user_id = uuid4()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token({"sub": str(user_id)}),
    )
    with (
        patch(
            "app.api.dependencies.UserRepository.get_by_id",
            new=AsyncMock(return_value=MagicMock(is_active=False)),
        ),
        pytest.raises(UnauthorizedException, match="Invalid access token"),
    ):
        await get_current_user(credentials=credentials, db=object())


@pytest.mark.asyncio
async def test_get_product_image_service_builds_dependencies():
    db = object()
    repository = MagicMock()
    s3_service = MagicMock()
    built_service = MagicMock()
    with (
        patch("app.api.dependencies.ProductImageRepository", return_value=repository),
        patch("app.api.dependencies.S3Service", return_value=s3_service),
        patch(
            "app.api.dependencies.ProductImageService",
            return_value=built_service,
        ) as service_class,
    ):
        result = await get_product_image_service(db=db)

    assert result is built_service
    service_class.assert_called_once_with(
        product_image_repo=repository,
        s3_service=s3_service,
    )

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.api.dependencies import get_current_user, get_product_image_service
from app.exceptions.custom import UnauthorizedException


def make_request(session_cookie=None):
    headers = []
    if session_cookie is not None:
        headers.append((b"cookie", f"session={session_cookie}".encode()))
    return Request({"type": "http", "headers": headers})


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_session_cookie():
    with pytest.raises(UnauthorizedException, match="Authentication required"):
        await get_current_user(make_request(), db=object(), redis=object())


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_session_cookie():
    with pytest.raises(UnauthorizedException, match="Invalid session"):
        await get_current_user(
            make_request("invalid-uuid"),
            db=object(),
            redis=object(),
        )


@pytest.mark.asyncio
async def test_get_current_user_returns_authenticated_session():
    session_id = uuid4()
    expected = {"user_id": str(uuid4())}
    with patch(
        "app.api.dependencies.AuthService.get_current_session",
        new=AsyncMock(return_value=expected),
    ) as get_session:
        result = await get_current_user(
            make_request(session_id),
            db=object(),
            redis=object(),
        )

    assert result == expected
    get_session.assert_awaited_once_with(session_id=session_id)


@pytest.mark.asyncio
async def test_get_product_image_service_builds_dependencies():
    db = object()
    repository = MagicMock()
    s3_service = MagicMock()
    built_service = MagicMock()
    with (
        patch(
            "app.api.dependencies.ProductImageRepository",
            return_value=repository,
        ) as repository_class,
        patch("app.api.dependencies.S3Service", return_value=s3_service),
        patch(
            "app.api.dependencies.ProductImageService",
            return_value=built_service,
        ) as service_class,
    ):
        result = await get_product_image_service(db=db)

    assert result is built_service
    repository_class.assert_called_once_with(db=db)
    service_class.assert_called_once_with(
        product_image_repo=repository,
        s3_service=s3_service,
    )

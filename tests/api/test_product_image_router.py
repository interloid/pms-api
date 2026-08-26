from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI

from app.api.dependencies import get_current_user, get_product_image_service
from app.api.v1.endpoints.product_image_router import router
from tests.api.conftest import ApiClient


@pytest.fixture
def service():
    return MagicMock()


@pytest.fixture
def client(service):
    app = FastAPI()
    app.include_router(router)

    async def current_user():
        return {"id": uuid4()}

    async def image_service():
        return service

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_product_image_service] = image_service
    return ApiClient(app)


def make_image(*, is_primary=False):
    return SimpleNamespace(
        id=uuid4(),
        url="https://cdn.example/image.png",
        is_primary=is_primary,
    )


def test_upload_product_image_returns_created_image(client, service):
    product_id = uuid4()
    image = make_image()
    service.upload_image = AsyncMock(return_value=image)

    response = client.post(
        f"/products/{product_id}/images?is_primary=true",
        files={"file": ("image.png", b"image-data", "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["id"] == str(image.id)
    assert service.upload_image.await_args.kwargs["product_id"] == product_id
    assert service.upload_image.await_args.kwargs["filename"] == "image.png"
    assert service.upload_image.await_args.kwargs["is_primary"] is True


def test_get_product_images_returns_all_images(client, service):
    product_id = uuid4()
    images = [make_image(), make_image(is_primary=True)]
    service.get_product_images = AsyncMock(return_value=images)

    response = client.get(f"/products/{product_id}/images")

    assert response.status_code == 200
    assert len(response.json()) == 2
    service.get_product_images.assert_awaited_once_with(product_id=product_id)


def test_set_primary_product_image_returns_updated_image(client, service):
    product_id = uuid4()
    image_id = uuid4()
    image = make_image(is_primary=True)
    service.set_primary_image = AsyncMock(return_value=image)

    response = client.patch(
        f"/products/{product_id}/images/{image_id}/primary"
    )

    assert response.status_code == 200
    assert response.json()["is_primary"] is True
    service.set_primary_image.assert_awaited_once_with(
        image_id=image_id,
        product_id=product_id,
    )


def test_delete_product_image_returns_no_content(client, service):
    product_id = uuid4()
    image_id = uuid4()
    service.delete_image = AsyncMock()

    response = client.delete(f"/products/{product_id}/images/{image_id}")

    assert response.status_code == 204
    assert response.content == b""
    service.delete_image.assert_awaited_once_with(
        image_id=image_id,
        product_id=product_id,
    )

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.dependencies import get_current_user
from app.api.v1.endpoints.product_router import router
from app.core.constants import RoleEnum
from app.db.session import get_db
from app.schemas.product_schema import ProductCreate
from tests.api.conftest import ApiClient


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)

    async def current_user():
        return SimpleNamespace(id=uuid4(), role=RoleEnum.ADMIN)

    async def database():
        return object()

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db] = database
    return ApiClient(app)


@pytest.fixture
def product():
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        name="Keyboard",
        sku="KEY-001",
        category=SimpleNamespace(name="Accessories"),
        price=Decimal("99.99"),
        stock=10,
        status="active",
        description="Mechanical keyboard",
        images=[],
        created_at=now,
        updated_at=now,
    )


def mock_product_service(**methods):
    service = MagicMock()
    for name, value in methods.items():
        setattr(service, name, value)
    return patch(
        "app.api.v1.endpoints.product_router.ProductService",
        return_value=service,
    ), service


def test_create_product_returns_created_product(client, product):
    service_patch, service = mock_product_service(
        create_product=AsyncMock(return_value=product),
    )
    with service_patch:
        response = client.post(
            "/products",
            data={
                "name": product.name,
                "sku": product.sku,
                "category_name": product.category.name,
                "price": str(product.price),
                "stock": str(product.stock),
                "status": product.status,
                "description": product.description,
            },
        )

    assert response.status_code == 201
    assert response.json()["data"]["id"] == str(product.id)
    service.create_product.assert_awaited_once()


def test_create_product_converts_schema_error_to_request_validation(client):
    with pytest.raises(ValidationError) as error:
        ProductCreate(
            name="",
            sku="KEY-001",
            category_name="Accessories",
            price="99.99",
            stock=10,
            status="active",
        )

    with patch(
        "app.api.v1.endpoints.product_router.ProductCreate",
        side_effect=error.value,
    ):
        response = client.post(
            "/products",
            data={
                "name": "Keyboard",
                "sku": "KEY-001",
                "category_name": "Accessories",
                "price": "99.99",
                "stock": "10",
                "status": "active",
            },
        )

    assert response.status_code == 422


def test_list_products_passes_filters_and_returns_pagination(client, product):
    service_patch, service = mock_product_service(
        list_products=AsyncMock(return_value=([product], 1)),
        calculate_total_pages=MagicMock(return_value=1),
    )
    with service_patch:
        response = client.get("/products?search=key&status=active&page=1&page_size=5")

    assert response.status_code == 200, response.text
    assert response.json()["pagination"] == {
        "page": 1,
        "page_size": 5,
        "total": 1,
        "total_pages": 1,
    }
    assert service.list_products.await_args.kwargs["search"] == "key"
    assert service.list_products.await_args.kwargs["status"] == "active"


def test_get_product_returns_requested_product(client, product):
    service_patch, service = mock_product_service(
        get_product=AsyncMock(return_value=product),
    )
    with service_patch:
        response = client.get(f"/products/{product.id}")

    assert response.status_code == 200
    assert response.json()["data"]["sku"] == product.sku
    service.get_product.assert_awaited_once_with(product_id=product.id)


def test_update_product_accepts_partial_update(client, product):
    service_patch, service = mock_product_service(
        update_product=AsyncMock(return_value=product),
    )
    with service_patch:
        response = client.patch(
            f"/products/{product.id}",
            data={
                "name": "Updated keyboard",
            },
            files={"images": ("image.png", b"image-data", "image/png")},
        )

    assert response.status_code == 200
    assert service.update_product.await_args.kwargs["payload"].name == (
        "Updated keyboard"
    )
    assert len(service.update_product.await_args.kwargs["images"]) == 1


def test_update_product_parses_image_ids_and_updates_product(client, product):
    removed_image_id = uuid4()
    primary_image_id = uuid4()
    service_patch, service = mock_product_service(
        update_product=AsyncMock(return_value=product),
    )
    with service_patch:
        response = client.patch(
            f"/products/{product.id}",
            data={
                "name": product.name,
                "sku": product.sku,
                "category_name": product.category.name,
                "price": str(product.price),
                "stock": str(product.stock),
                "status": product.status,
                "removed_image_ids": f'["{removed_image_id}"]',
                "primary_image_id": str(primary_image_id),
            },
            files={"images": ("image.png", b"image-data", "image/png")},
        )

    assert response.status_code == 200, response.text
    assert service.update_product.await_args.kwargs["removed_image_ids"] == [
        removed_image_id
    ]
    assert service.update_product.await_args.kwargs["primary_image_id"] == (
        primary_image_id
    )
    uploaded_images = service.update_product.await_args.kwargs["images"]
    assert len(uploaded_images) == 1
    assert uploaded_images[0].filename == "image.png"


def test_update_product_rejects_non_list_removed_image_ids(client, product):
    response = client.patch(
        f"/products/{product.id}",
        data={"removed_image_ids": '{"id": "value"}'},
        files={"images": ("image.png", b"image-data", "image/png")},
    )

    assert response.status_code == 422


def test_update_product_rejects_invalid_removed_image_ids(client, product):
    response = client.patch(
        f"/products/{product.id}",
        data={"removed_image_ids": "not-json"},
    )

    assert response.status_code == 422


def test_delete_product_returns_no_content(client, product):
    service_patch, service = mock_product_service(delete_product=AsyncMock())
    with service_patch:
        response = client.delete(f"/products/{product.id}")

    assert response.status_code == 204
    assert response.content == b""
    service.delete_product.assert_awaited_once_with(product_id=product.id)

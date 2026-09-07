from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.endpoints.product_router import (
    to_product_response,
    to_product_responses,
)
from app.models.category_model import Category
from app.models.product_image_model import ProductImage
from app.models.product_model import Product


def make_product(*, object_keys: list[str]) -> Product:
    product_id = uuid4()
    product = Product(
        id=product_id,
        name="Test product",
        sku=f"SKU-{uuid4()}",
        price=Decimal("10.00"),
        stock=5,
        status="active",
    )
    product.category = Category(id=uuid4(), name="Test category")
    product.images = [
        ProductImage(
            id=uuid4(),
            product_id=product_id,
            object_key=object_key,
            is_primary=index == 0,
        )
        for index, object_key in enumerate(object_keys)
    ]
    return product


@pytest.mark.asyncio
async def test_to_product_responses_generates_urls_in_one_batch() -> None:
    first_product = make_product(object_keys=["products/first.jpg"])
    second_product = make_product(
        object_keys=["products/second.jpg", "products/third.jpg"]
    )
    expected_urls = {
        "products/first.jpg": "https://signed.example/first.jpg",
        "products/second.jpg": "https://signed.example/second.jpg",
        "products/third.jpg": "https://signed.example/third.jpg",
    }
    s3_service = AsyncMock()
    s3_service.generate_presigned_urls.return_value = expected_urls

    responses = await to_product_responses(
        products=[first_product, second_product],
        s3_service=s3_service,
    )

    s3_service.generate_presigned_urls.assert_awaited_once_with(
        object_keys=[
            "products/first.jpg",
            "products/second.jpg",
            "products/third.jpg",
        ]
    )
    assert [image.url for response in responses for image in response.images] == list(
        expected_urls.values()
    )


@pytest.mark.asyncio
async def test_to_product_response_returns_single_product_response() -> None:
    product = make_product(object_keys=["products/image.jpg"])
    s3_service = AsyncMock()
    s3_service.generate_presigned_urls.return_value = {
        "products/image.jpg": "https://signed.example/image.jpg"
    }

    response = await to_product_response(
        product=product,
        s3_service=s3_service,
    )

    assert response.id == product.id
    assert response.images[0].url == "https://signed.example/image.jpg"
    s3_service.generate_presigned_urls.assert_awaited_once_with(
        object_keys=["products/image.jpg"]
    )

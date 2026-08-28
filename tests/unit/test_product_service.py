from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.constants import ProductImageConstants
from app.exceptions.custom import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.models.category_model import Category
from app.models.product_image_model import ProductImage
from app.models.product_model import Product
from app.schemas.product_schema import ProductUpdate
from app.services.product_service import ProductService


@pytest.mark.asyncio
async def test_get_product_returns_product():
    db = MagicMock()

    service = ProductService(db)

    product_id = uuid4()
    product = Product(
        id=product_id,
        name="iphone 15",
        sku="IPHONE-15",
    )

    service.product_repo.get_by_id = AsyncMock(
        return_value=product,
    )

    result = await service.get_product(product_id=product_id)

    assert result is product

    service.product_repo.get_by_id.assert_awaited_once_with(
        product_id=product_id,
    )


@pytest.mark.asyncio
async def test_get_product_raises_not_found_when_product_does_not_exist():
    db = MagicMock()

    service = ProductService(db)

    product_id = uuid4()

    service.product_repo.get_by_id = AsyncMock(
        return_value=None,
    )

    with pytest.raises(NotFoundException) as exc_info:
        await service.get_product(
            product_id=product_id,
        )

    assert str(exc_info.value) == "Product not found"

    service.product_repo.get_by_id.assert_awaited_once_with(
        product_id=product_id,
    )


@pytest.mark.asyncio
async def test_delete_product_raises_not_found_when_product_does_not_exist():
    db = MagicMock()

    service = ProductService(db)

    product_id = uuid4()

    service.product_repo.get_by_id = AsyncMock(
        return_value=None,
    )

    service.product_repo.delete = AsyncMock()

    with pytest.raises(NotFoundException) as exc_info:
        await service.delete_product(
            product_id=product_id,
        )

    assert str(exc_info.value) == "Product not found"

    service.product_repo.get_by_id.assert_awaited_once_with(
        product_id=product_id,
    )

    service.product_repo.delete.assert_not_awaited()


# Product not found


@pytest.mark.asyncio
async def test_update_product_raises_not_found_when_product_does_not_exist():
    db = MagicMock()

    service = ProductService(db)

    product_id = uuid4()

    service.product_repo.get_by_id = AsyncMock(
        return_value=None,
    )

    service.product_repo.update = AsyncMock()

    payload = ProductUpdate(
        name="Updated Product",
    )

    with pytest.raises(NotFoundException) as exc_info:
        await service.update_product(
            product_id=product_id,
            payload=payload,
            images=[],
        )

    assert str(exc_info.value) == "Product not found"

    service.product_repo.get_by_id.assert_awaited_once_with(
        product_id=product_id,
    )

    service.product_repo.update.assert_not_awaited()


# Normal update


@pytest.mark.asyncio
async def test_update_product_updates_product():
    db = MagicMock()
    db.refresh = AsyncMock()

    service = ProductService(db)

    product_id = uuid4()

    product = Product(
        id=product_id,
        name="iPhone 15",
        price=Decimal("799.99"),
        sku="IPHONE-15",
    )

    updated_product = Product(
        id=product_id,
        name="iPhone 15 Pro",
        price=Decimal("999.99"),
        stock=15,
        sku="IPHONE-15",
    )

    service.product_repo.get_by_id = AsyncMock(
        side_effect=[
            product,
            updated_product,
        ],
    )

    service.product_repo.update = AsyncMock(
        return_value=updated_product,
    )

    payload = ProductUpdate(
        name="iPhone 15 Pro",
        price=Decimal("999.99"),
        stock=15,
    )

    result = await service.update_product(
        product_id=product_id,
        payload=payload,
        images=[],
    )

    assert result is updated_product

    assert product.name == "iPhone 15 Pro"
    assert product.price == Decimal("999.99")
    assert product.stock == 15

    service.product_repo.update.assert_awaited_once_with(
        product=product,
    )

    assert service.product_repo.get_by_id.await_count == 2


@pytest.mark.asyncio
async def test_update_product_rejects_total_images_above_limit():
    db = MagicMock()
    service = ProductService(db)
    product_id = uuid4()
    product = Product(
        id=product_id,
        name="iPhone 15",
        sku="IPHONE-15",
    )
    product.images = [
        ProductImage(id=uuid4(), product_id=product_id)
        for _ in range(ProductImageConstants.MAX_IMAGES)
    ]
    new_image = MagicMock()
    new_image.filename = "new.png"
    new_image.content_type = "image/png"
    new_image.size = 100

    service.product_repo.get_by_id = AsyncMock(return_value=product)
    service.product_repo.update = AsyncMock()

    with pytest.raises(BadRequestException, match="Maximum 6 images are allowed"):
        await service.update_product(
            product_id=product_id,
            payload=ProductUpdate(name="Updated product"),
            images=[new_image],
        )

    service.product_repo.update.assert_not_awaited()


# SKU conflict


@pytest.mark.asyncio
async def test_update_product_raises_conflict_when_sku_already_exists():
    db = MagicMock()

    service = ProductService(db)

    product_id = uuid4()
    existing_product_id = uuid4()

    product = Product(
        id=product_id,
        name="iPhone 15",
        sku="IPHONE-15",
    )

    existing_product = Product(
        id=existing_product_id,
        name="Samsung",
        sku="SAMSUNG-S23",
    )

    service.product_repo.get_by_id = AsyncMock(
        return_value=product,
    )

    service.product_repo.get_by_sku = AsyncMock(
        return_value=existing_product,
    )

    service.product_repo.update = AsyncMock()

    payload = ProductUpdate(
        sku="SAMSUNG-S23",
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.update_product(
            product_id=product_id,
            payload=payload,
            images=[],
        )

    assert str(exc_info.value) == ("Product with this SKU already exists")

    service.product_repo.get_by_id.assert_awaited_once_with(
        product_id=product_id,
    )

    service.product_repo.get_by_sku.assert_awaited_once_with(
        sku="SAMSUNG-S23",
    )

    service.product_repo.update.assert_not_awaited()


# Category doesn't exist


@pytest.mark.asyncio
async def test_update_product_raises_not_found_when_category_does_not_exist():
    db = MagicMock()

    service = ProductService(db)

    product_id = uuid4()

    product = Product(
        id=product_id,
        name="iPhone 15",
        sku="IPHONE-15",
    )

    service.product_repo.get_by_id = AsyncMock(
        return_value=product,
    )

    service.category_repo.get_by_name = AsyncMock(
        return_value=None,
    )

    service.product_repo.update = AsyncMock()

    payload = ProductUpdate(
        category_name="Non Existing Category",
    )

    with pytest.raises(NotFoundException) as exc_info:
        await service.update_product(
            product_id=product_id,
            payload=payload,
            images=[],
        )

    assert str(exc_info.value) == "Category not found"

    service.category_repo.get_by_name.assert_awaited_once_with(
        name="Non Existing Category",
    )

    service.product_repo.update.assert_not_awaited()


# Category exists


@pytest.mark.asyncio
async def test_update_product_updates_category():
    db = MagicMock()
    db.refresh = AsyncMock()

    service = ProductService(db)

    product_id = uuid4()
    category_id = uuid4()

    product = Product(
        id=product_id,
        name="iPhone 15",
        sku="IPHONE-15",
    )

    category = Category(
        id=category_id,
        name="Electronics",
    )

    service.product_repo.get_by_id = AsyncMock(
        side_effect=[
            product,
            product,
        ],
    )

    service.category_repo.get_by_name = AsyncMock(
        return_value=category,
    )

    service.product_repo.update = AsyncMock(
        return_value=product,
    )

    payload = ProductUpdate(
        category_name=" Electronics ",
    )

    result = await service.update_product(
        product_id=product_id,
        payload=payload,
        images=[],
    )

    assert result is product
    assert product.category_id == category_id

    service.category_repo.get_by_name.assert_awaited_once_with(
        name="Electronics",
    )

    service.product_repo.update.assert_awaited_once_with(
        product=product,
    )

    service.product_repo.get_by_id.assert_awaited()


# list_products with default parameters


@pytest.mark.asyncio
async def test_list_products_returns_products_and_total():
    db = MagicMock()

    service = ProductService(db)

    products = [
        Product(
            id=uuid4(),
            name="iPhone 15",
            sku="IPHONE-15",
        ),
        Product(
            id=uuid4(),
            name="Samsung S23",
            sku="SAMSUNG-S23",
        ),
    ]

    service.paginate = AsyncMock(
        return_value=(products, 2),
    )

    result = await service.list_products()

    assert result == (products, 2)

    service.paginate.assert_awaited_once()

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.product_model import Product
from app.repositories.product_repo import ProductRepository


@pytest.mark.asyncio
async def test_get_by_id_returns_product():
    db = MagicMock()
    product_id = uuid4()

    product = Product(
        id=product_id,
        name="iPhone 15",
        sku="IPHONE-15",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = product

    db.execute = AsyncMock(return_value=result)

    repo = ProductRepository(db)

    returned_product = await repo.get_by_id(
        product_id=product_id,
    )

    assert returned_product is product

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_product_does_not_exist():
    db = MagicMock()
    product_id = uuid4()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(return_value=result)

    repo = ProductRepository(db)

    returned_product = await repo.get_by_id(
        product_id=product_id,
    )

    assert returned_product is None

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_sku_returns_product():
    db = MagicMock()

    product = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = product

    db.execute = AsyncMock(return_value=result)

    repo = ProductRepository(db)

    returned_product = await repo.get_by_sku(
        sku="IPHONE-15",
    )

    assert returned_product is product

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_sku_returns_none_when_product_does_not_exist():
    db = MagicMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(return_value=result)

    repo = ProductRepository(db)

    returned_product = await repo.get_by_sku(
        sku="UNKNOWN-SKU",
    )

    assert returned_product is None

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_returns_created_product():
    db = MagicMock()
    db.flush = AsyncMock()

    repo = ProductRepository(db)

    product = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    repo.get_by_id = AsyncMock(
        return_value=product,
    )

    result = await repo.create(
        product=product,
    )

    assert result is product

    db.add.assert_called_once_with(product)

    db.flush.assert_awaited_once()

    repo.get_by_id.assert_awaited_once_with(
        product_id=product.id,
    )


@pytest.mark.asyncio
async def test_create_raises_runtime_error_when_product_cannot_be_retrieved():
    db = MagicMock()
    db.flush = AsyncMock()

    repo = ProductRepository(db)

    product = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    repo.get_by_id = AsyncMock(
        return_value=None,
    )

    with pytest.raises(
        RuntimeError,
        match="Created product could not be retrieved",
    ):
        await repo.create(
            product=product,
        )

    db.add.assert_called_once_with(product)

    db.flush.assert_awaited_once()

    repo.get_by_id.assert_awaited_once_with(
        product_id=product.id,
    )


@pytest.mark.asyncio
async def test_update_returns_updated_product():
    db = MagicMock()
    db.flush = AsyncMock()

    repo = ProductRepository(db)

    product_id = uuid4()

    product = Product(
        id=product_id,
        name="iPhone 15",
        sku="IPHONE-15",
    )

    updated_product = Product(
        id=product_id,
        name="iPhone 15 Pro",
        sku="IPHONE-15",
    )

    repo.get_by_id = AsyncMock(
        return_value=updated_product,
    )

    result = await repo.update(
        product=product,
    )

    assert result is updated_product

    db.flush.assert_awaited_once()

    repo.get_by_id.assert_awaited_once_with(
        product_id=product_id,
    )


@pytest.mark.asyncio
async def test_update_raises_runtime_error_when_product_cannot_be_retrieved():
    db = MagicMock()
    db.flush = AsyncMock()

    repo = ProductRepository(db)

    product = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    repo.get_by_id = AsyncMock(
        return_value=None,
    )

    with pytest.raises(
        RuntimeError,
        match="Updated product could not be retrieved",
    ):
        await repo.update(
            product=product,
        )

    db.flush.assert_awaited_once()

    repo.get_by_id.assert_awaited_once_with(
        product_id=product.id,
    )


@pytest.mark.asyncio
async def test_delete_removes_product():
    db = MagicMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()

    repo = ProductRepository(db)

    product = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    result = await repo.delete(
        product=product,
    )

    assert result is None

    db.delete.assert_awaited_once_with(product)

    db.flush.assert_awaited_once()


def mock_list_result(products):
    result = MagicMock()

    scalars = MagicMock()
    unique = MagicMock()

    unique.all.return_value = products
    scalars.unique.return_value = unique
    result.scalars.return_value = scalars

    return result


@pytest.mark.asyncio
async def test_list_returns_products_and_total():
    db = MagicMock()

    product1 = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    product2 = Product(
        id=uuid4(),
        name="Samsung S24",
        sku="SAMSUNG-S24",
    )

    count_result = MagicMock()
    count_result.scalar_one.return_value = 2

    products_result = mock_list_result(
        [product1, product2],
    )

    db.execute = AsyncMock(
        side_effect=[
            count_result,
            products_result,
        ],
    )

    repo = ProductRepository(db)

    products, total = await repo.list()

    assert products == [product1, product2]
    assert total == 2

    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_list_with_search_returns_matching_products():
    db = MagicMock()

    product = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    products_result = mock_list_result([product])

    db.execute = AsyncMock(
        side_effect=[
            count_result,
            products_result,
        ],
    )

    repo = ProductRepository(db)

    products, total = await repo.list(
        search="iphone",
    )

    assert products == [product]
    assert total == 1

    assert db.execute.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sort_order",
    [
        "asc",
        "desc",
    ],
)
async def test_list_with_sort_order_returns_products(sort_order):
    db = MagicMock()

    product = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    products_result = mock_list_result([product])

    db.execute = AsyncMock(
        side_effect=[
            count_result,
            products_result,
        ],
    )

    repo = ProductRepository(db)

    products, total = await repo.list(
        sort_by="name",
        sort_order=sort_order,
    )

    assert products == [product]
    assert total == 1

    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_list_uses_updated_at_for_invalid_sort_by():
    db = MagicMock()

    product = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    products_result = mock_list_result([product])

    db.execute = AsyncMock(
        side_effect=[
            count_result,
            products_result,
        ],
    )

    repo = ProductRepository(db)

    products, total = await repo.list(
        sort_by="invalid",
    )

    assert products == [product]
    assert total == 1

    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_list_applies_pagination():
    db = MagicMock()

    product = Product(
        id=uuid4(),
        name="iPhone 15",
        sku="IPHONE-15",
    )

    count_result = MagicMock()
    count_result.scalar_one.return_value = 25

    products_result = mock_list_result([product])

    db.execute = AsyncMock(
        side_effect=[
            count_result,
            products_result,
        ],
    )

    repo = ProductRepository(db)

    products, total = await repo.list(
        page=2,
        page_size=10,
    )

    assert products == [product]
    assert total == 25

    assert db.execute.await_count == 2

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.constants import ProductStatusEnum
from app.exceptions.custom import BadRequestException
from app.models.product_model import Product
from app.services.product_service import ProductService

# Default parameters


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


# Search
@pytest.mark.asyncio
async def test_list_products_with_search():
    db = MagicMock()

    service = ProductService(db)

    products = [
        Product(
            id=uuid4(),
            name="iPhone 15",
            sku="IPHONE-15",
        ),
    ]

    service.apply_search = MagicMock(
        side_effect=lambda stmt, *, search_expression: stmt,
    )

    service.paginate = AsyncMock(
        return_value=(products, 1),
    )

    result = await service.list_products(
        search="iphone",
    )

    assert result == (products, 1)

    service.apply_search.assert_called_once()

    service.paginate.assert_awaited_once()


# Category filter


@pytest.mark.asyncio
async def test_list_products_with_category_filter():
    db = MagicMock()

    service = ProductService(db)

    products = [
        Product(
            id=uuid4(),
            name="iPhone 15",
            sku="IPHONE-15",
        ),
    ]

    service.apply_filters = MagicMock(
        side_effect=lambda stmt, *, filters: stmt,
    )

    service.paginate = AsyncMock(
        return_value=(products, 1),
    )

    result = await service.list_products(
        category_name="Electronics",
    )

    assert result == (products, 1)

    service.apply_filters.assert_called_once()

    filters = service.apply_filters.call_args.kwargs["filters"]

    assert len(filters) == 1

    service.paginate.assert_awaited_once()


# Status filter
@pytest.mark.asyncio
async def test_list_products_with_status_filter():
    db = MagicMock()

    service = ProductService(db)

    service.apply_filters = MagicMock(
        side_effect=lambda stmt, *, filters: stmt,
    )

    service.paginate = AsyncMock(
        return_value=([], 0),
    )

    result = await service.list_products(
        status=ProductStatusEnum.ACTIVE,
    )

    assert result == ([], 0)

    service.apply_filters.assert_called_once()

    filters = service.apply_filters.call_args.kwargs["filters"]

    assert len(filters) == 1


# Minimum price


@pytest.mark.asyncio
async def test_list_products_with_min_price():
    db = MagicMock()

    service = ProductService(db)

    service.apply_filters = MagicMock(
        side_effect=lambda stmt, *, filters: stmt,
    )

    service.paginate = AsyncMock(
        return_value=([], 0),
    )

    result = await service.list_products(
        min_price=Decimal("100.00"),
    )

    assert result == ([], 0)

    service.apply_filters.assert_called_once()

    filters = service.apply_filters.call_args.kwargs["filters"]

    assert len(filters) == 1


# Maximum price
@pytest.mark.asyncio
async def test_list_products_with_max_price():
    db = MagicMock()

    service = ProductService(db)

    service.apply_filters = MagicMock(
        side_effect=lambda stmt, *, filters: stmt,
    )

    service.paginate = AsyncMock(
        return_value=([], 0),
    )

    result = await service.list_products(
        max_price=Decimal("1000.00"),
    )

    assert result == ([], 0)

    service.apply_filters.assert_called_once()

    filters = service.apply_filters.call_args.kwargs["filters"]

    assert len(filters) == 1


# In-stock filter


@pytest.mark.asyncio
async def test_list_products_with_in_stock_filter():
    db = MagicMock()

    service = ProductService(db)

    service.apply_filters = MagicMock(
        side_effect=lambda stmt, *, filters: stmt,
    )

    service.paginate = AsyncMock(
        return_value=([], 0),
    )

    result = await service.list_products(
        in_stock=True,
    )

    assert result == ([], 0)

    service.apply_filters.assert_called_once()

    filters = service.apply_filters.call_args.kwargs["filters"]

    assert len(filters) == 1


# Out-of-stock filter


@pytest.mark.asyncio
async def test_list_products_with_out_of_stock_filter():
    db = MagicMock()

    service = ProductService(db)

    service.apply_filters = MagicMock(
        side_effect=lambda stmt, *, filters: stmt,
    )

    service.paginate = AsyncMock(
        return_value=([], 0),
    )

    result = await service.list_products(
        in_stock=False,
    )

    assert result == ([], 0)

    service.apply_filters.assert_called_once()

    filters = service.apply_filters.call_args.kwargs["filters"]

    assert len(filters) == 1


# Multiple filters


@pytest.mark.asyncio
async def test_list_products_with_multiple_filters():
    db = MagicMock()

    service = ProductService(db)

    service.apply_filters = MagicMock(
        side_effect=lambda stmt, *, filters: stmt,
    )

    service.paginate = AsyncMock(
        return_value=([], 0),
    )

    result = await service.list_products(
        category_name="Electronics",
        status=ProductStatusEnum.ACTIVE,
        min_price=Decimal("100.00"),
        max_price=Decimal("1000.00"),
        in_stock=True,
    )

    assert result == ([], 0)

    service.apply_filters.assert_called_once()

    filters = service.apply_filters.call_args.kwargs["filters"]

    assert len(filters) == 5


# Sorting


@pytest.mark.asyncio
async def test_list_products_with_sorting():
    db = MagicMock()

    service = ProductService(db)

    service.validate_sort_order = MagicMock(
        return_value="asc",
    )

    service.resolve_sort_column = MagicMock(
        return_value=Product.name,
    )

    service.apply_sorting = MagicMock(
        side_effect=lambda stmt, *, sort_column, sort_order: stmt,
    )

    service.paginate = AsyncMock(
        return_value=([], 0),
    )

    result = await service.list_products(
        sort_by="name",
        sort_order="asc",
    )

    assert result == ([], 0)

    service.validate_sort_order.assert_called_once_with(
        "asc",
    )

    service.resolve_sort_column.assert_called_once_with(
        sort_by="name",
        sort_fields=service.SORT_FIELDS,
        default_sort=service.DEFAULT_SORT,
    )

    service.apply_sorting.assert_called_once_with(
        service.apply_sorting.call_args.args[0],
        sort_column=Product.name,
        sort_order="asc",
    )


# Pagination parameters are passed correctly


@pytest.mark.asyncio
async def test_list_products_passes_pagination_parameters():
    db = MagicMock()

    service = ProductService(db)

    service.paginate = AsyncMock(
        return_value=([], 25),
    )

    result = await service.list_products(
        page=3,
        page_size=20,
    )

    assert result == ([], 25)

    paginate_kwargs = service.paginate.call_args.kwargs

    assert paginate_kwargs["page"] == 3
    assert paginate_kwargs["page_size"] == 20


# Pagination validation failure


@pytest.mark.asyncio
async def test_list_products_rejects_invalid_pagination():
    db = MagicMock()

    service = ProductService(db)

    service.paginate = AsyncMock()

    with pytest.raises(BadRequestException):
        await service.list_products(
            page=0,
            page_size=10,
        )

    service.paginate.assert_not_awaited()


# Invalid sort field falls back to default


@pytest.mark.asyncio
async def test_list_products_uses_default_sort_for_unknown_sort_field():
    db = MagicMock()

    service = ProductService(db)

    service.resolve_sort_column = MagicMock(
        return_value=Product.updated_at,
    )

    service.apply_sorting = MagicMock(
        side_effect=lambda stmt, *, sort_column, sort_order: stmt,
    )

    service.paginate = AsyncMock(
        return_value=([], 0),
    )

    result = await service.list_products(
        sort_by="unknown",
    )

    assert result == ([], 0)

    service.resolve_sort_column.assert_called_once_with(
        sort_by="unknown",
        sort_fields=service.SORT_FIELDS,
        default_sort=service.DEFAULT_SORT,
    )

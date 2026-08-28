from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.category_model import Category
from app.repositories.category_repo import CategoryRepository


@pytest.mark.asyncio
async def test_get_by_id_returns_category():
    db = MagicMock()

    category_id = uuid4()

    category = Category(
        id=category_id,
        name="Electronics",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = category

    db.execute = AsyncMock(
        return_value=result,
    )

    repo = CategoryRepository(db)

    returned_category = await repo.get_by_id(
        category_id=category_id,
    )

    assert returned_category is category

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_category_does_not_exist():
    db = MagicMock()

    category_id = uuid4()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(
        return_value=result,
    )

    repo = CategoryRepository(db)

    returned_category = await repo.get_by_id(
        category_id=category_id,
    )

    assert returned_category is None

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_name_returns_category():
    db = MagicMock()

    category = Category(
        id=uuid4(),
        name="Electronics",
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = category

    db.execute = AsyncMock(
        return_value=result,
    )

    repo = CategoryRepository(db)

    returned_category = await repo.get_by_name(
        name="Electronics",
    )

    assert returned_category is category

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_name_returns_none_when_category_does_not_exist():
    db = MagicMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(
        return_value=result,
    )

    repo = CategoryRepository(db)

    returned_category = await repo.get_by_name(
        name="Unknown Category",
    )

    assert returned_category is None

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_all_returns_categories():
    db = MagicMock()

    categories = [
        Category(
            id=uuid4(),
            name="Electronics",
        ),
        Category(
            id=uuid4(),
            name="Furniture",
        ),
    ]

    scalars_result = MagicMock()
    scalars_result.all.return_value = categories

    result = MagicMock()
    result.scalars.return_value = scalars_result

    db.execute = AsyncMock(
        return_value=result,
    )

    repo = CategoryRepository(db)

    returned_categories = await repo.get_all()

    assert returned_categories == categories

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_all_returns_empty_list_when_no_categories_exist():
    db = MagicMock()

    scalars_result = MagicMock()
    scalars_result.all.return_value = []

    result = MagicMock()
    result.scalars.return_value = scalars_result

    db.execute = AsyncMock(
        return_value=result,
    )

    repo = CategoryRepository(db)

    returned_categories = await repo.get_all()

    assert returned_categories == []

    db.execute.assert_awaited_once()

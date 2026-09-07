from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category_model import Category
from app.services.category_service import CategoryService


@pytest.mark.asyncio
async def test_get_categories_returns_first_page(
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    categories = [
        Category(
            id=uuid4(),
            name=f"Zulu-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Alpha-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Middle-{search_value}",
        ),
    ]

    db_session.add_all(categories)
    await db_session.commit()

    service = CategoryService(db=db_session)

    returned_categories, total = await service.get_categories(
        search=search_value,
        page=1,
        page_size=2,
    )

    returned_names = [category.name for category in returned_categories]

    assert total == 3
    assert len(returned_categories) == 2
    assert returned_names == [
        f"Alpha-{search_value}",
        f"Middle-{search_value}",
    ]


@pytest.mark.asyncio
async def test_get_categories_returns_second_page(
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    categories = [
        Category(
            id=uuid4(),
            name=f"Zulu-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Alpha-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Middle-{search_value}",
        ),
    ]

    db_session.add_all(categories)
    await db_session.commit()

    service = CategoryService(db=db_session)

    returned_categories, total = await service.get_categories(
        search=search_value,
        page=2,
        page_size=2,
    )

    assert total == 3
    assert len(returned_categories) == 1
    assert returned_categories[0].name == (f"Zulu-{search_value}")


@pytest.mark.asyncio
async def test_get_categories_filters_by_search(
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    matching_categories = [
        Category(
            id=uuid4(),
            name=f"Phone-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Accessories-{search_value}",
        ),
    ]

    unrelated_category = Category(
        id=uuid4(),
        name=f"Furniture-{uuid4().hex[:8]}",
    )

    db_session.add_all(
        [
            *matching_categories,
            unrelated_category,
        ]
    )
    await db_session.commit()

    service = CategoryService(db=db_session)

    returned_categories, total = await service.get_categories(
        search=search_value,
        page=1,
        page_size=10,
    )

    returned_ids = {category.id for category in returned_categories}

    expected_ids = {category.id for category in matching_categories}

    assert total == 2
    assert returned_ids == expected_ids
    assert unrelated_category.id not in returned_ids


@pytest.mark.asyncio
async def test_get_categories_search_is_case_insensitive(
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    category = Category(
        id=uuid4(),
        name=f"MixedCase-{search_value}",
    )

    db_session.add(category)
    await db_session.commit()

    service = CategoryService(db=db_session)

    returned_categories, total = await service.get_categories(
        search=(f"mixedcase-{search_value}"),
        page=1,
        page_size=10,
    )

    assert total == 1
    assert len(returned_categories) == 1
    assert returned_categories[0].id == category.id


@pytest.mark.asyncio
async def test_get_categories_returns_empty_page_when_no_match(
    db_session: AsyncSession,
) -> None:
    service = CategoryService(db=db_session)

    returned_categories, total = await service.get_categories(
        search=f"missing-{uuid4().hex}",
        page=1,
        page_size=10,
    )

    assert returned_categories == []
    assert total == 0


@pytest.mark.asyncio
async def test_get_categories_returns_empty_page_when_page_is_out_of_range(
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    category = Category(
        id=uuid4(),
        name=f"Electronics-{search_value}",
    )

    db_session.add(category)
    await db_session.commit()

    service = CategoryService(db=db_session)

    returned_categories, total = await service.get_categories(
        search=search_value,
        page=2,
        page_size=10,
    )

    assert returned_categories == []
    assert total == 1


@pytest.mark.asyncio
async def test_get_categories_respects_page_size(
    db_session: AsyncSession,
) -> None:
    search_value = uuid4().hex[:8]

    categories = [
        Category(
            id=uuid4(),
            name=f"Category-A-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Category-B-{search_value}",
        ),
        Category(
            id=uuid4(),
            name=f"Category-C-{search_value}",
        ),
    ]

    db_session.add_all(categories)
    await db_session.commit()

    service = CategoryService(db=db_session)

    returned_categories, total = await service.get_categories(
        search=search_value,
        page=1,
        page_size=1,
    )

    assert total == 3
    assert len(returned_categories) == 1
    assert returned_categories[0].name == (f"Category-A-{search_value}")

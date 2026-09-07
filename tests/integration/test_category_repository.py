from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category_model import Category
from app.repositories.category_repo import CategoryRepository


@pytest.mark.asyncio
async def test_get_by_id_returns_category(
    db_session: AsyncSession,
) -> None:
    category = Category(
        id=uuid4(),
        name=f"Electronics-{uuid4().hex[:8]}",
    )

    db_session.add(category)
    await db_session.commit()

    category_id = category.id

    repo = CategoryRepository(db_session)

    returned_category = await repo.get_by_id(
        category_id=category_id,
    )

    assert returned_category is not None
    assert returned_category.id == category_id
    assert returned_category.name == category.name


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_category_does_not_exist(
    db_session: AsyncSession,
) -> None:
    repo = CategoryRepository(db_session)

    returned_category = await repo.get_by_id(
        category_id=uuid4(),
    )

    assert returned_category is None


@pytest.mark.asyncio
async def test_get_by_name_returns_category(
    db_session: AsyncSession,
) -> None:
    category_name = f"Furniture-{uuid4().hex[:8]}"

    category = Category(
        id=uuid4(),
        name=category_name,
    )

    db_session.add(category)
    await db_session.commit()

    repo = CategoryRepository(db_session)

    returned_category = await repo.get_by_name(
        name=category_name,
    )

    assert returned_category is not None
    assert returned_category.id == category.id
    assert returned_category.name == category_name


@pytest.mark.asyncio
async def test_get_by_name_returns_none_when_category_does_not_exist(
    db_session: AsyncSession,
) -> None:
    missing_name = f"Missing-{uuid4().hex[:8]}"

    repo = CategoryRepository(db_session)

    returned_category = await repo.get_by_name(
        name=missing_name,
    )

    assert returned_category is None


@pytest.mark.asyncio
async def test_list_statement_returns_categories_in_name_order(
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

    repo = CategoryRepository(db_session)

    stmt = repo.get_all(
        search=search_value,
    )

    result = await db_session.execute(stmt)

    returned_categories = list(result.scalars().all())

    returned_names = [category.name for category in returned_categories]

    assert returned_names == [
        f"Alpha-{search_value}",
        f"Middle-{search_value}",
        f"Zulu-{search_value}",
    ]


@pytest.mark.asyncio
async def test_list_statement_filters_categories_by_search(
    db_session: AsyncSession,
) -> None:
    unique_value = uuid4().hex[:8]

    matching_category = Category(
        id=uuid4(),
        name=f"Camera-{unique_value}",
    )
    unrelated_category = Category(
        id=uuid4(),
        name=f"Furniture-{uuid4().hex[:8]}",
    )

    db_session.add_all(
        [
            matching_category,
            unrelated_category,
        ]
    )
    await db_session.commit()

    repo = CategoryRepository(db_session)

    stmt = repo.get_all(
        search=unique_value,
    )

    result = await db_session.execute(stmt)

    returned_categories = list(result.scalars().all())

    assert len(returned_categories) == 1
    assert returned_categories[0].id == (matching_category.id)


@pytest.mark.asyncio
async def test_list_statement_search_is_case_insensitive(
    db_session: AsyncSession,
) -> None:
    unique_value = uuid4().hex[:8]

    category = Category(
        id=uuid4(),
        name=f"MixedCase-{unique_value}",
    )

    db_session.add(category)
    await db_session.commit()

    repo = CategoryRepository(db_session)

    stmt = repo.get_all(
        search=f"mixedcase-{unique_value}",
    )

    result = await db_session.execute(stmt)

    returned_categories = list(result.scalars().all())

    assert len(returned_categories) == 1
    assert returned_categories[0].id == category.id


@pytest.mark.asyncio
async def test_list_statement_returns_empty_list_when_search_has_no_match(
    db_session: AsyncSession,
) -> None:
    repo = CategoryRepository(db_session)

    stmt = repo.get_all(
        search=f"missing-{uuid4().hex}",
    )

    result = await db_session.execute(stmt)

    returned_categories = list(result.scalars().all())

    assert returned_categories == []

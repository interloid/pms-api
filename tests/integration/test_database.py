from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.category_model import Category


@pytest.mark.asyncio
async def test_database_connection(
    test_engine: AsyncEngine,
) -> None:
    async with test_engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))

    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_session(db_session: AsyncSession):
    result = await db_session.execute(
        text("SELECT 1"),
    )
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_database_commit_inside_transaction(
    db_session: AsyncSession,
) -> None:
    category = Category(
        name=f"pytest-rollback-{uuid4().hex[:12]}",
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)

    result = await db_session.execute(
        select(Category).where(
            Category.id == category.id,
        )
    )

    stored_category = result.scalar_one_or_none()

    assert stored_category is not None
    assert stored_category.name == category.name

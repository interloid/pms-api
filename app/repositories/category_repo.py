from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category_model import Category


class CategoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, category_id: UUID) -> Category | None:
        stmt = select(Category).where(Category.id == category_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Category | None:
        stmt = select(Category).where(Category.name == name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, search: str | None = None) -> list[Category]:

        stmt = select(Category)

        if search:
            normalized_search = search.strip()

            if normalized_search:
                stmt = stmt.where(Category.name.ilike(f"%{normalized_search}%"))

        return stmt.order_by(Category.name.asc())

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category_model import Category
from app.repositories.category_repo import CategoryRepository
from app.services.base_service import BaseService


class CategoryService(BaseService[Category]):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.category_repo = CategoryRepository(db)

    async def get_categories(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Category], int]:

        self.validate_pagination(
            page=page,
            page_size=page_size,
        )

        category_stmt = self.category_repo.get_all(search=search)

        return await self.paginate(category_stmt, page=page, page_size=page_size)

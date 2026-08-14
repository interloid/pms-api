from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import ceil
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import PaginationEnum
from app.exceptions.custom import BadRequestException


class BaseService[T]:
    def __init__(
        self,
        db: AsyncSession,
    ) -> None:
        self.db = db

    @staticmethod
    def validate_pagination(
        *,
        page: int,
        page_size: int,
    ) -> None:
        if page < PaginationEnum.DEFAULT_PAGE:
            raise BadRequestException(
                message="Page must be greater than or equal to 1",
            )

        if page_size < 1:
            raise BadRequestException(
                message="Page size must be greater than or equal to 1",
            )

        if page_size > PaginationEnum.MAX_PAGE_SIZE:
            raise BadRequestException(
                message=(
                    "Page size must be less than or equal to "
                    f"{PaginationEnum.MAX_PAGE_SIZE}"
                ),
            )

    @staticmethod
    def calculate_offset(
        *,
        page: int,
        page_size: int,
    ) -> int:
        return (page - 1) * page_size

    @staticmethod
    def calculate_total_pages(
        *,
        total: int,
        page_size: int,
    ) -> int:
        if total == 0:
            return 0

        return ceil(total / page_size)

    @staticmethod
    def validate_sort_order(
        sort_order: str,
    ) -> str:
        normalized_order = sort_order.strip().lower()

        if normalized_order not in {"asc", "desc"}:
            raise BadRequestException(
                message="Sort order must be either 'asc' or 'desc'",
            )

        return normalized_order

    @staticmethod
    def resolve_sort_column(
        *,
        sort_by: str,
        sort_fields: Mapping[str, Any],
        default_sort: str,
    ) -> Any:
        normalized_sort = sort_by.strip().lower()

        sort_column = sort_fields.get(normalized_sort)

        if sort_column is None:
            sort_column = sort_fields.get(default_sort)

        if sort_column is None:
            raise BadRequestException(
                message="Invalid sort field",
                # Your current BadRequestException does not accept
                # details, so keep this simple for now.
            )

        return sort_column

    @staticmethod
    def apply_sorting(
        stmt: Select,
        *,
        sort_column: Any,
        sort_order: str,
    ) -> Select:
        if sort_order == "asc":
            return stmt.order_by(sort_column.asc())

        return stmt.order_by(sort_column.desc())

    @staticmethod
    def apply_search(
        stmt: Select,
        *,
        search_expression: Any | None,
    ) -> Select:
        if search_expression is None:
            return stmt

        return stmt.where(search_expression)

    @staticmethod
    def apply_filters(
        stmt: Select,
        *,
        filters: Sequence[Any] | None = None,
    ) -> Select:
        if not filters:
            return stmt

        return stmt.where(*filters)

    async def paginate(
        self,
        stmt: Select,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[T], int]:
        """
        Execute a SELECT statement with pagination and return:

            (items, total)

        The supplied statement should contain all filtering conditions.
        Sorting should normally already be applied before this method.
        """

        self.validate_pagination(
            page=page,
            page_size=page_size,
        )

        count_stmt = select(
            func.count(),
        ).select_from(
            stmt.order_by(None).subquery(),
        )

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()

        offset = self.calculate_offset(
            page=page,
            page_size=page_size,
        )

        paginated_stmt = stmt.offset(offset).limit(page_size)

        result = await self.db.execute(paginated_stmt)

        items = list(result.scalars().unique().all())

        return items, total

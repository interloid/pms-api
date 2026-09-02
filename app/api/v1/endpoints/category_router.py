from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_permission
from app.api.dependencies import get_current_user
from app.core.constants import PaginationEnum, PermissionEnum
from app.db.session import get_db
from app.exceptions.global_exception import CRUD_ERROR_RESPONSES
from app.models.category_model import Category
from app.schemas.category_schema import CategoryResponse
from app.schemas.response import PaginatedResponse, PaginationMeta
from app.services.category_service import CategoryService

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
    dependencies=[Depends(get_current_user)],
)


def to_category_response(category: Category) -> CategoryResponse:
    return CategoryResponse(
        id=category.id,
        name=category.name,
    )


@router.get(
    "",
    dependencies=[Depends(require_permission(PermissionEnum.VIEW_PRODUCTS))],
    response_model=PaginatedResponse[CategoryResponse],
    status_code=status.HTTP_200_OK,
    responses=CRUD_ERROR_RESPONSES,
)
async def get_categories(
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    page: int = Query(
        default=PaginationEnum.DEFAULT_PAGE,
        ge=1,
    ),
    page_size: int = Query(
        default=PaginationEnum.DEFAULT_PAGE_SIZE,
        ge=1,
        le=PaginationEnum.MAX_PAGE_SIZE,
    ),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CategoryResponse]:

    category_service = CategoryService(db=db)

    categories, total = await category_service.get_categories(
        search=search, page=page, page_size=page_size
    )

    items = [to_category_response(category) for category in categories]

    total_pages = category_service.calculate_total_pages(
        total=total, page_size=page_size
    )

    return PaginatedResponse(
        message="Categories retrieved successfully",
        data=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )

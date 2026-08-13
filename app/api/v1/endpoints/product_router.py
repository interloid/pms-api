from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    PaginationEnum,
    ProductStatusEnum,
)
from app.db.session import get_db
from app.exceptions.global_exception import CRUD_ERROR_RESPONSES
from app.schemas.product_schema import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.schemas.response import (
    ApiResponse,
    PaginatedResponse,
    PaginationMeta,
)
from app.services.product_service import ProductService


router = APIRouter(
    prefix="/products",
    tags=["Products"],
)


@router.post(
    "",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    responses=CRUD_ERROR_RESPONSES,
)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProductResponse]:
    product_service = ProductService(
        db=db,
    )

    product = await product_service.create_product(
        payload=payload,
    )

    return ApiResponse(
        message="Product created successfully",
        data=ProductResponse.model_validate(product),
    )


@router.get(
    "",
    response_model=PaginatedResponse[ProductResponse],
    status_code=status.HTTP_200_OK,
    responses=CRUD_ERROR_RESPONSES,
)
async def list_products(
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    category_id: UUID | None = Query(
        default=None,
    ),
    status_filter: ProductStatusEnum | None = Query(
        default=None,
        alias="status",
    ),
    min_price: Decimal | None = Query(
        default=None,
        ge=0,
    ),
    max_price: Decimal | None = Query(
        default=None,
        ge=0,
    ),
    in_stock: bool | None = Query(
        default=None,
    ),
    sort: str = Query(
        default="updated",
        min_length=1,
        max_length=50,
    ),
    order: str = Query(
        default="desc",
        min_length=1,
        max_length=4,
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
) -> PaginatedResponse[ProductResponse]:
    product_service = ProductService(
        db=db,
    )

    products, total = await product_service.list_products(
        search=search,
        category_id=category_id,
        status=status_filter,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        sort_by=sort,
        sort_order=order,
        page=page,
        page_size=page_size,
    )

    items = [
        ProductResponse.model_validate(product)
        for product in products
    ]

    total_pages = product_service.calculate_total_pages(
        total=total,
        page_size=page_size,
    )

    return PaginatedResponse(
        message="Products retrieved successfully",
        data=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/{product_id}",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_200_OK,
    responses=CRUD_ERROR_RESPONSES,
)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProductResponse]:
    product_service = ProductService(
        db=db,
    )

    product = await product_service.get_product(
        product_id=product_id,
    )

    return ApiResponse(
        message="Product retrieved successfully",
        data=ProductResponse.model_validate(product),
    )


@router.patch(
    "/{product_id}",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_200_OK,
    responses=CRUD_ERROR_RESPONSES,
)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProductResponse]:
    product_service = ProductService(
        db=db,
    )

    product = await product_service.update_product(
        product_id=product_id,
        payload=payload,
    )

    return ApiResponse(
        message="Product updated successfully",
        data=ProductResponse.model_validate(product),
    )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=CRUD_ERROR_RESPONSES,
)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    product_service = ProductService(
        db=db,
    )

    await product_service.delete_product(
        product_id=product_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
    
    
    
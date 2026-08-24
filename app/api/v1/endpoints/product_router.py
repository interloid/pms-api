from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.constants import (
    PaginationEnum,
    ProductStatusEnum,
)
from app.db.session import get_db
from app.exceptions.global_exception import CRUD_ERROR_RESPONSES
from app.models.product_model import Product
from app.schemas.product_image_schema import ProductImageResponse
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
    prefix="/products", tags=["Products"], dependencies=[Depends(get_current_user)]
)


def to_product_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        name=product.name,
        sku=product.sku,
        category_name=product.category.name,
        price=product.price,
        stock=product.stock,
        status=ProductStatusEnum(product.status),
        description=product.description,
        images=[ProductImageResponse.model_validate(image) for image in product.images],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.post(
    "",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_201_CREATED,
    responses=CRUD_ERROR_RESPONSES,
)
async def create_product(
    name: Annotated[str, Form(...)],
    sku: Annotated[str, Form(...)],
    category_name: Annotated[str, Form(...)],
    price: Annotated[Decimal, Form(...)],
    stock: Annotated[int, Form(...)],
    status: Annotated[ProductStatusEnum, Form(...)],
    description: Annotated[str | None, Form()] = None,
    images: Annotated[list[UploadFile], File()] = [],
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProductResponse]:

    try:
        payload = ProductCreate(
            name=name,
            sku=sku,
            category_name=category_name,
            price=price,
            stock=stock,
            status=status,
            description=description,
        )

        product_service = ProductService(db=db)

        product = await product_service.create_product(
            payload=payload,
            images=images,
        )

        return ApiResponse(
            message="Product created successfully",
            data=to_product_response(product),
        )

    except ValidationError as exc:
        raise RequestValidationError(
            exc.errors(),
        ) from exc


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
    category_name: str | None = Query(
        default=None,
        min_length=1,
        max_length=255,
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
        category_name=category_name,
        status=status_filter,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        sort_by=sort,
        sort_order=order,
        page=page,
        page_size=page_size,
    )

    items = [to_product_response(product) for product in products]

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
        message="Product retrieved successfully", data=to_product_response(product)
    )


@router.patch(
    "/{product_id}",
    response_model=ApiResponse[ProductResponse],
    status_code=status.HTTP_200_OK,
    responses=CRUD_ERROR_RESPONSES,
)
async def update_product(
    product_id: UUID,
    name: Annotated[str | None, Form()] = None,
    sku: Annotated[str | None, Form()] = None,
    category_name: Annotated[str | None, Form()] = None,
    price: Annotated[Decimal | None, Form()] = None,
    stock: Annotated[int | None, Form()] = None,
    status: Annotated[ProductStatusEnum | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    primary_image_id: Annotated[UUID | None, Form()] = None,
    images: Annotated[list[UploadFile], File()] = [],
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ProductResponse]:

    try:
        payload = ProductUpdate(
            name=name,
            sku=sku,
            category_name=category_name,
            price=price,
            stock=stock,
            status=status,
            description=description,
        )

        product_service = ProductService(
            db=db,
        )

        product = await product_service.update_product(
            product_id=product_id,
            payload=payload,
            images=images,
            primary_image_id=primary_image_id,
        )

        return ApiResponse(
            message="Product updated successfully",
            data=to_product_response(product),
        )

    except ValidationError as exc:
        raise RequestValidationError(
            exc.errors(),
        ) from exc


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

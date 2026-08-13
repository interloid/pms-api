from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.constants import ProductStatusEnum
from app.schemas.common import BaseSchema
from app.schemas.product_image_schema import ProductImageResponse


class ProductCreate(BaseSchema):
    name: str = Field(
        min_length=1,
        max_length=255,
    )
    sku: str = Field(
        min_length=1,
        max_length=255,
    )
    category_id: UUID
    price: Decimal = Field(
        ge=0,
    )
    stock: int = Field(
        ge=0,
    )
    status: ProductStatusEnum
    description: str | None = None


class ProductUpdate(BaseSchema):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    sku: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    category_id: UUID | None = None
    price: Decimal | None = Field(
        default=None,
        ge=0,
    )
    stock: int | None = Field(
        default=None,
        ge=0,
    )
    status: ProductStatusEnum | None = None
    description: str | None = None


class ProductResponse(BaseSchema):
    id: UUID
    name: str
    sku: str
    category_id: UUID
    price: Decimal
    stock: int
    status: ProductStatusEnum
    description: str | None
    images: list[ProductImageResponse]
    
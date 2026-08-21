from decimal import Decimal
from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

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
    category_name: str
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
    category_name: str | None = None
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

    @model_validator(mode="after")
    def validate_update_fields(self):
        non_nullable_fields = {
            "name",
            "sku",
            "category_name",
            "price",
            "stock",
            "status",
        }
        for field_name in self.model_fields_set & non_nullable_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        return self


class ProductResponse(BaseSchema):
    id: UUID
    name: str
    sku: str
    category_name: str
    price: Decimal
    stock: int
    status: ProductStatusEnum
    description: str | None
    images: list[ProductImageResponse]
    created_at: datetime | None
    updated_at: datetime | None

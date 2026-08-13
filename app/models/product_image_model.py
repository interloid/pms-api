from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import BaseEntity

if TYPE_CHECKING:
    from app.models.product_model import Product


class ProductImage(BaseEntity):
    __tablename__ = "product_images"

    __table_args__ = (
        Index(
            "uq_product_primary_image",
            "product_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )

    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="images",
    )

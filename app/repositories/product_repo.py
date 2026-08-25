from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product_model import Product


class ProductRepository:
    def __init__(
        self,
        db: AsyncSession,
    ) -> None:
        self.db = db

    async def create(
        self,
        product: Product,
    ) -> Product:
        self.db.add(product)

        await self.db.flush()

        created_product = await self.get_by_id(
            product_id=product.id,
        )

        if created_product is None:
            raise RuntimeError(
                "Created product could not be retrieved",
            )

        return created_product

    async def get_by_id(
        self,
        product_id: UUID,
    ) -> Product | None:
        stmt = (
            select(Product)
            .options(
                selectinload(Product.images),
                selectinload(Product.category),
            )
            .where(Product.id == product_id)
        )

        result = await self.db.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_sku(
        self,
        sku: str,
    ) -> Product | None:
        stmt = select(Product).where(Product.sku == sku)

        result = await self.db.execute(stmt)

        return result.scalar_one_or_none()

    async def update(
        self,
        product: Product,
    ) -> Product:
        await self.db.flush()

        updated_product = await self.get_by_id(
            product_id=product.id,
        )

        if updated_product is None:
            raise RuntimeError(
                "Updated product could not be retrieved",
            )

        return updated_product

    async def delete(
        self,
        product: Product,
    ) -> None:
        await self.db.delete(product)

        await self.db.flush()

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_image_model import ProductImage


class ProductImageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def create(self, image: ProductImage) -> ProductImage:
        self.db.add(image)
        await self.db.flush()
        await self.db.refresh(image)
        return image


    async def get_by_id(self,image_id: UUID) -> ProductImage | None:
        stmt = select(ProductImage).where(ProductImage.id == image_id,)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


    async def get_by_id_and_product(self,image_id: UUID,product_id: UUID) -> ProductImage | None:
        stmt = select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


    async def get_by_product_id(self,product_id: UUID) -> list[ProductImage]:
        stmt = (
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(
                ProductImage.is_primary.desc(),
                ProductImage.created_at.asc(),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


    async def unset_primary(self,product_id: UUID) -> None:
        stmt = (
            update(ProductImage)
            .where(ProductImage.product_id == product_id)
            .values(is_primary=False)
        )
        await self.db.execute(stmt)


    async def set_primary(self,image: ProductImage) -> ProductImage:
        await self.unset_primary(image.product_id)
        image.is_primary = True
        await self.db.flush()
        await self.db.refresh(image)
        return image


    async def delete(self, image: ProductImage) -> None:
        await self.db.delete(image)
        await self.db.flush()
        
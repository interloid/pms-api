from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
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
            )
            .where(Product.id == product_id)
        )

        result = await self.db.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_sku(
        self,
        sku: str,
    ) -> Product | None:
        stmt = (
            select(Product)
            .where(Product.sku == sku)
        )

        result = await self.db.execute(stmt)

        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        search: str | None = None,
        category_id: UUID | None = None,
        status: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        in_stock: bool | None = None,
        sort_by: str = "updated",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Product], int]:

        stmt = (
            select(Product)
            .options(
                selectinload(Product.images),
            )
        )

        if search:
            search_pattern = f"%{search}%"

            stmt = stmt.where(
                or_(
                    Product.name.ilike(search_pattern),
                    Product.sku.ilike(search_pattern),
                )
            )

        if category_id is not None:
            stmt = stmt.where(
                Product.category_id == category_id,
            )

        if status is not None:
            stmt = stmt.where(
                Product.status == status,
            )

        if min_price is not None:
            stmt = stmt.where(
                Product.price >= min_price,
            )

        if max_price is not None:
            stmt = stmt.where(
                Product.price <= max_price,
            )

        if in_stock is True:
            stmt = stmt.where(
                Product.stock > 0,
            )

        elif in_stock is False:
            stmt = stmt.where(
                Product.stock == 0,
            )

        sort_column = {
            "name": Product.name,
            "sku": Product.sku,
            "category": Product.category_id,
            "price": Product.price,
            "stock": Product.stock,
            "status": Product.status,
            "updated": Product.updated_at,
        }.get(
            sort_by,
            Product.updated_at,
        )

        if sort_order == "asc":
            stmt = stmt.order_by(
                sort_column.asc(),
            )
        else:
            stmt = stmt.order_by(
                sort_column.desc(),
            )

        count_stmt = select(
            func.count(),
        ).select_from(
            stmt.order_by(None).subquery(),
        )

        count_result = await self.db.execute(
            count_stmt,
        )

        total = count_result.scalar_one()

        offset = (page - 1) * page_size

        stmt = (
            stmt
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(stmt)

        products = list(
            result.scalars().unique().all()
        )

        return products, total

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
        
        
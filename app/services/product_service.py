from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import ProductStatusEnum
from app.exceptions.custom import ConflictException, NotFoundException
from app.models.product_model import Product
from app.repositories.category_repo import CategoryRepository
from app.repositories.product_repo import ProductRepository
from app.schemas.product_schema import ProductCreate, ProductUpdate
from app.services.base_service import BaseService


class ProductService(BaseService[Product]):
    SORT_FIELDS = {
        "name": Product.name,
        "sku": Product.sku,
        "category": Product.category_id,
        "price": Product.price,
        "stock": Product.stock,
        "status": Product.status,
        "updated": Product.updated_at,
    }

    DEFAULT_SORT = "updated"

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

        self.product_repo = ProductRepository(db)
        self.category_repo = CategoryRepository(db)

    async def create_product(self, payload: ProductCreate) -> Product:

        existing_product = await self.product_repo.get_by_sku(sku=payload.sku)

        if existing_product is not None:
            raise ConflictException(
                message="Product with this SKU already exists",
            )

        category_name = payload.category_name.strip()

        category = await self.category_repo.get_by_name(name=category_name)

        if category is None:
            raise NotFoundException(message="Category not found")

        product = Product(
            name=payload.name,
            sku=payload.sku,
            category_id=category.id,
            price=payload.price,
            stock=payload.stock,
            status=payload.status,
            description=payload.description,
        )

        try:
            return await self.product_repo.create(product=product)

        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictException(
                message="Product with this SKU already exists"
            ) from exc

    async def get_product(self, product_id: UUID) -> Product:

        product = await self.product_repo.get_by_id(product_id=product_id)

        if product is None:
            raise NotFoundException(message="Product not found")

        return product

    async def list_products(
        self,
        *,
        search: str | None = None,
        category_name: str | None = None,
        status: ProductStatusEnum | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        in_stock: bool | None = None,
        sort_by: str = DEFAULT_SORT,
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Product], int]:

        self.validate_pagination(
            page=page,
            page_size=page_size,
        )

        normalized_sort_order = self.validate_sort_order(
            sort_order,
        )

        sort_column = self.resolve_sort_column(
            sort_by=sort_by,
            sort_fields=self.SORT_FIELDS,
            default_sort=self.DEFAULT_SORT,
        )

        stmt = select(Product).options(
            selectinload(Product.images), selectinload(Product.category)
        )

        if search:
            search_pattern = f"%{search.strip()}%"

            search_expression = or_(
                Product.name.ilike(search_pattern),
                Product.sku.ilike(search_pattern),
            )

            stmt = self.apply_search(
                stmt,
                search_expression=search_expression,
            )

        filters = []

        if category_name is not None:
            filters.append(
                Product.category.has(
                    name=category_name,
                ),
            )

        if status is not None:
            filters.append(
                Product.status == status,
            )

        if min_price is not None:
            filters.append(
                Product.price >= min_price,
            )

        if max_price is not None:
            filters.append(
                Product.price <= max_price,
            )

        if in_stock is True:
            filters.append(
                Product.stock > 0,
            )

        elif in_stock is False:
            filters.append(
                Product.stock == 0,
            )

        stmt = self.apply_filters(
            stmt,
            filters=filters,
        )

        stmt = self.apply_sorting(
            stmt,
            sort_column=sort_column,
            sort_order=normalized_sort_order,
        )

        return await self.paginate(
            stmt,
            page=page,
            page_size=page_size,
        )

    async def update_product(
        self,
        product_id: UUID,
        payload: ProductUpdate,
    ) -> Product:

        product = await self.product_repo.get_by_id(
            product_id=product_id,
        )

        if product is None:
            raise NotFoundException(
                message="Product not found",
            )

        updates = payload.model_dump(
            exclude_unset=True,
        )

        if not updates:
            return product

        if "sku" in updates and updates["sku"] != product.sku:
            existing_product = await self.product_repo.get_by_sku(
                sku=updates["sku"],
            )

            if existing_product is not None and existing_product.id != product.id:
                raise ConflictException(
                    message="Product with this SKU already exists",
                )

        if "category_name" in updates:
            category_name = updates["category_name"].strip()

            category = await self.category_repo.get_by_name(
                name=category_name,
            )

            if category is None:
                raise NotFoundException(
                    message="Category not found",
                )

            product.category_id = category.id

            del updates["category_name"]

        for field, value in updates.items():
            setattr(
                product,
                field,
                value,
            )

        try:
            return await self.product_repo.update(product=product)

        except IntegrityError as exc:
            raise ConflictException(
                message=(
                    "Product could not be updated because of a conflicting resource"
                ),
            ) from exc

    async def delete_product(self, product_id: UUID) -> None:

        product = await self.product_repo.get_by_id(product_id=product_id)

        if product is None:
            raise NotFoundException(message="Product not found")

        await self.product_repo.delete(product=product)

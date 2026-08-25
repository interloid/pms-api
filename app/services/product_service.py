from decimal import Decimal
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import (
    ProductImageConstants,
    ProductStatusEnum,
)
from app.core.logging import get_logger
from app.core.s3 import S3Service
from app.exceptions.custom import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.models.product_model import Product
from app.repositories.category_repo import CategoryRepository
from app.repositories.product_image_repo import ProductImageRepository
from app.repositories.product_repo import ProductRepository
from app.schemas.product_schema import ProductCreate, ProductUpdate
from app.services.base_service import BaseService
from app.services.product_image_service import ProductImageService

logger = get_logger(__name__)


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
        self.product_image_service = ProductImageService(
            product_image_repo=ProductImageRepository(db),
            s3_service=S3Service(),
        )

    async def _validate_product_images(
        self,
        images: list[UploadFile],
    ) -> None:

        if len(images) > ProductImageConstants.MAX_IMAGES:
            logger.warning(f"Maximum{ProductImageConstants.MAX_IMAGES} are not allowed")
            raise BadRequestException(
                message=(
                    f"Maximum {ProductImageConstants.MAX_IMAGES} images are allowed"
                ),
            )

        for image in images:
            if not image.filename:
                logger.warning(
                    "Image filename is required | filename=%s",f"{image.filename}"
                )
                raise BadRequestException(
                    message="Image filename is required",
                )

            if not image.content_type:
                logger.warning(
                    f"Content type could not be determined for"
                    f"{image.filename}'"
                    "content_type=%s",
                    image.content_type,
                )
                raise BadRequestException(
                    message=(
                        f"Content type could not be determined for '{image.filename}'"
                    ),
                )

            if image.content_type not in ProductImageConstants.ALLOWED_CONTENT_TYPES:
                logger.warning(
                    "Unsupported image type content_type=%s", f"{image.content_type}"
                )
                raise BadRequestException(
                    message=(
                        f"Unsupported image type '{image.content_type}'. "
                        "Allowed types: JPEG, PNG, and WebP"
                    ),
                )
            if image.size is None:
                logger.warning("Could not determine size for size=%s", f"{image.size}")
                raise BadRequestException(
                    message=(f"Could not determine size for '{image.filename}'"),
                )

            if image.size > ProductImageConstants.MAX_FILE_SIZE:
                logger.warning(
                    "Image exceeds the maximum size of 5 MB size=%s", f"{image.size}"
                )
                raise BadRequestException(
                    message=(
                        f"Image '{image.filename}' exceeds the maximum size of 5 MB"
                    ),
                )
                
    async def _cleanup_s3(self, object_keys: list[str]) -> None:
        for object_key in object_keys:
            try:
                await self.product_image_service.s3_service.delete_file(
                    object_key=object_key,
                )
            except Exception:
                logger.exception(
                    "Failed to clean up S3 object | object_key=%s",
                    object_key,
                )

    async def create_product(
        self, payload: ProductCreate, images: list[UploadFile]
    ) -> Product:

        await self._validate_product_images(images)

        existing_product = await self.product_repo.get_by_sku(sku=payload.sku)

        if existing_product is not None:
            logger.warning("Product with this SKU already exists | sku=%s", payload.sku)
            raise ConflictException(
                message="Product with this SKU already exists",
            )

        category_name = payload.category_name.strip()

        category = await self.category_repo.get_by_name(name=category_name)

        if category is None:
            logger.warning("Category not found | category=%s", category)
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

        uploaded_object_keys: list[str] = []

        try:
            product = await self.product_repo.create(
                product=product,
            )

            for index, image in enumerate(images):
                product_image = await self.product_image_service.upload_image(
                    product_id=product.id,
                    file=image.file,
                    filename=image.filename or "image",
                    content_type=image.content_type or "application/octet-stream",
                    is_primary=(index == 0),
                )

                uploaded_object_keys.append(product_image.object_key)

            product = await self.product_repo.get_by_id(
                product_id=product.id,
            )

            if product is None:
                logger.warning("Product not found after creation")
                raise RuntimeError("Product not found after creation")

            return product

        except Exception:
            await self.db.rollback()

            for object_key in uploaded_object_keys:
                try:
                    await self.product_image_service.s3_service.delete_file(
                        object_key=object_key,
                    )
                except Exception:
                    logger.exception(
                        "Failed to clean up S3 object after "
                        "product creation failure | object_key=%s",
                        object_key,
                    )
            raise

    async def get_product(self, product_id: UUID) -> Product:

        product = await self.product_repo.get_by_id(product_id=product_id)

        if product is None:
            logger.warning("Product not found | product_id=%s", product_id)
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

        if min_price is not None and max_price is not None and min_price > max_price:
            logger.warning(
                "Minimum price cannot be greater than maximum price | "
                "min_price=%s | max_price=%s",
                min_price,
                max_price,
            )
            raise BadRequestException(
                message="Minimum price cannot be greater than maximum price",
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
        images: list[UploadFile],
        removed_image_ids: list[UUID] | None = None,
        primary_image_id: UUID | None = None,
    ) -> Product:

        if images:
            await self._validate_product_images(images)

        product = await self.product_repo.get_by_id(
            product_id=product_id,
        )

        if product is None:
            logger.warning("product not found | product_id=%s", product_id)
            raise NotFoundException(
                message="Product not found",
            )

        updates = payload.model_dump(exclude_unset=True)

        if "sku" in updates and updates["sku"] != product.sku:
            existing_product = await self.product_repo.get_by_sku(
                sku=updates["sku"],
            )

            if existing_product is not None and existing_product.id != product.id:
                logger.warning(
                    "Product with this SKU already exists | sku=%s", updates["sku"]
                )
                raise ConflictException(
                    message="Product with this SKU already exists",
                )

        if "category_name" in updates:
            category_name = updates["category_name"].strip()

            category = await self.category_repo.get_by_name(
                name=category_name,
            )

            if category is None:
                logger.warning("Category not found | category=%s", category)
                raise NotFoundException(
                    message="Category not found",
                )

            product.category_id = category.id
            del updates["category_name"]

        for field, value in updates.items():
            setattr(product, field, value)

        images_to_delete: list[str] = []
        uploaded_object_keys: list[str] = []

        try:
            product = await self.product_repo.update(
                product=product,
            )
            
            if removed_image_ids:
                for image_id in removed_image_ids:
                    image = await self.product_image_service.get_image(
                        image_id=image_id,
                        product_id=product_id,
                    )

                    images_to_delete.append(image.object_key)

                    await self.product_image_service.product_image_repo.delete(
                        image
                    )

            if images:
                uploaded_images = await self.product_image_service.add_images(
                    product_id=product.id,
                    images=images,
                )
                uploaded_object_keys.extend(
                    image.object_key 
                    for image in uploaded_images
                )

            if primary_image_id is not None:
                await self.product_image_service.set_primary_image(
                    image_id=primary_image_id,
                    product_id=product.id,
                )

            product = await self.product_repo.get_by_id(product.id)
            
            if product is None:
                raise NotFoundException(message="Product not found")
            
            await self._cleanup_s3(images_to_delete)

            return product

        except IntegrityError as exc:
            await self._cleanup_s3(uploaded_object_keys)

            logger.warning(
                "Product could not be updated because of a conflicting resource"
            )
            raise ConflictException(
                message=(
                    "Product could not be updated because of a conflicting resource"
                ),
            ) from exc

        except Exception:
            await self._cleanup_s3(uploaded_object_keys)
            raise

    async def delete_product(self, product_id: UUID) -> None:

        product = await self.product_repo.get_by_id(
            product_id=product_id,
        )

        if product is None:
            logger.warning("product not found product_id=%s", product_id)
            raise NotFoundException(message="Product not found")

        await self.product_image_service.delete_by_product_id(
            product_id=product_id,
        )

        await self.product_repo.delete(product=product)

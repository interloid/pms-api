import hashlib
from typing import BinaryIO
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.core.logging import get_logger
from app.core.s3 import S3Service
from app.exceptions.custom import NotFoundException
from app.models.product_image_model import ProductImage
from app.repositories.product_image_repo import ProductImageRepository

logger = get_logger(__name__)


class ProductImageService:
    def __init__(
        self, product_image_repo: ProductImageRepository, s3_service: S3Service
    ) -> None:

        self.product_image_repo = product_image_repo
        self.s3_service = s3_service

    async def upload_image(
        self,
        *,
        product_id: UUID,
        file: BinaryIO,
        filename: str,
        content_type: str,
        content_hash: str | None = None,
        is_primary: bool = False,
    ) -> ProductImage:

        if content_hash is None:
            digest = hashlib.sha256()
            file.seek(0)
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
            file.seek(0)
            content_hash = digest.hexdigest()

        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""

        object_key = (
            f"products/{product_id}/images/{uuid4()}.{extension}"
            if extension
            else f"products/{product_id}/images/{uuid4()}"
        )

        url = await self.s3_service.upload_file(
            file=file,
            object_key=object_key,
            content_type=content_type,
        )

        try:
            image = ProductImage(
                product_id=product_id,
                url=url,
                object_key=object_key,
                content_hash=content_hash,
                is_primary=False,
            )

            image = await self.product_image_repo.create(image)

            if is_primary:
                image = await self.product_image_repo.set_primary(image)

            return image
        except Exception:
            try:
                await self.s3_service.delete_file(object_key=object_key)
            except Exception:
                logger.exception(
                    "Failed to clean up S3 object after database failure | "
                    "object_key=%s",
                    object_key,
                )
            raise

    async def add_images(
        self,
        *,
        product_id: UUID,
        images: list[UploadFile],
        content_hashes: list[str],
    ) -> list[ProductImage]:

        uploaded_images: list[ProductImage] = []
        uploaded_object_keys: list[str] = []

        try:
            for image, content_hash in zip(images, content_hashes, strict=True):
                product_image = await self.upload_image(
                    product_id=product_id,
                    file=image.file,
                    filename=image.filename or "image",
                    content_type=image.content_type or "application/octet-stream",
                    content_hash=content_hash,
                )

                uploaded_images.append(product_image)
                uploaded_object_keys.append(product_image.object_key)

            return uploaded_images

        except Exception:
            for product_image in uploaded_images:
                try:
                    await self.product_image_repo.delete(product_image)
                except Exception:
                    logger.exception(
                        "Failed to clean up ProductImage after "
                        "image upload failure | image_id=%s",
                        product_image.id,
                    )

            for object_key in uploaded_object_keys:
                try:
                    await self.s3_service.delete_file(
                        object_key=object_key,
                    )
                except Exception:
                    logger.exception(
                        "Failed to clean up S3 object after "
                        "image upload failure | object_key=%s",
                        object_key,
                    )
            raise

    async def get_image(
        self,
        *,
        image_id: UUID,
        product_id: UUID,
    ) -> ProductImage:

        image = await self.product_image_repo.get_by_id_and_product(
            image_id=image_id,
            product_id=product_id,
        )

        if image is None:
            logger.warning(
                "Product image not found | product_id=%s | image_id=%s",
                product_id,
                image_id,
            )
            raise NotFoundException(message="Product image not found")

        return image

    async def get_product_images(self, *, product_id: UUID) -> list[ProductImage]:

        return await self.product_image_repo.get_by_product_id(
            product_id=product_id,
        )

    async def set_primary_image(
        self,
        *,
        image_id: UUID,
        product_id: UUID,
    ) -> ProductImage:

        image = await self.get_image(image_id=image_id, product_id=product_id)

        if image.is_primary:
            return image

        return await self.product_image_repo.set_primary(image)

    async def delete_image(
        self,
        *,
        image_id: UUID,
        product_id: UUID,
    ) -> None:

        image = await self.get_image(
            image_id=image_id,
            product_id=product_id,
        )

        object_key = image.object_key

        await self.product_image_repo.delete(image)

        try:
            await self.s3_service.delete_file(object_key=object_key)

        except Exception:
            logger.exception(
                "Failed to delete S3 object after deleting "
                "ProductImage | object_key=%s",
                object_key,
            )

    async def delete_by_product_id(self, product_id: UUID) -> None:

        images = await self.product_image_repo.get_by_product_id(
            product_id=product_id,
        )

        for image in images:
            await self.s3_service.delete_file(
                object_key=image.object_key,
            )

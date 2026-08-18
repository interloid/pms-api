from typing import BinaryIO
from uuid import UUID, uuid4

from app.core.s3 import S3Service
from app.exceptions.custom import NotFoundException
from app.models.product_image_model import ProductImage
from app.repositories.product_image_repo import ProductImageRepository


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
        is_primary: bool = False,
    ) -> ProductImage:

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

        image = ProductImage(
            product_id=product_id,
            url=url,
            object_key=object_key,
            is_primary=is_primary,
        )

        image = await self.product_image_repo.create(image)

        if is_primary:
            image = await self.product_image_repo.set_primary(image)

        return image

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

        await self.s3_service.delete_file(object_key=image.object_key)

        await self.product_image_repo.delete(image)

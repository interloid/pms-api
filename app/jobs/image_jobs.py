from typing import Any
from uuid import UUID

from arq import Retry
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.constants import ProductImageConstants
from app.core.logging import get_logger
from app.core.settings import settings
from app.models.product_image_model import ProductImage
from app.repositories.product_image_repo import ProductImageRepository
from app.repositories.product_repo import ProductRepository
from app.schemas.image_jobs_schema import ProductImageUploadPayload

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/webp": {"webp"},
}


async def upload_product_images(
    ctx: dict[str, Any],
    product_id: str,
    images: list[ProductImageUploadPayload],
) -> dict[str, Any]:

    if not images:
        return {
            "product_id": product_id,
            "uploaded": 0,
            "image_ids": [],
        }

    if len(images) > ProductImageConstants.MAX_IMAGES:
        raise ValueError("Maximum product image limit exceeded")

    product_uuid = UUID(product_id)

    primary_count = sum(1 for image in images if image["is_primary"])

    if primary_count > 1:
        raise ValueError("Only one image can be primary")

    prepared_images: list[dict[str, Any]] = []

    for image in images:
        image_id = UUID(image["image_id"])
        extension = image["extension"].lower().lstrip(".")
        content_type = image["content_type"]
        content_hash = image["content_hash"].lower()
        staging_key = image["staging_key"]

        allowed_extensions = ALLOWED_EXTENSIONS.get(content_type)

        if allowed_extensions is None or extension not in allowed_extensions:
            raise ValueError("Image extension does not match its content type")

        if len(content_hash) != 64 or any(
            character not in "0123456789abcdef" for character in content_hash
        ):
            raise ValueError("Invalid SHA-256 content hash")

        expected_staging_key = (
            f"staging/products/{product_uuid}/images/{image_id}.{extension}"
        )

        if staging_key != expected_staging_key:
            raise ValueError("Invalid image staging key")

        final_key = f"products/{product_uuid}/images/{image_id}.{extension}"

        prepared_images.append(
            {
                "image_id": image_id,
                "staging_key": staging_key,
                "final_key": final_key,
                "content_type": content_type,
                "content_hash": content_hash,
                "is_primary": image["is_primary"],
            }
        )

    image_ids = [image["image_id"] for image in prepared_images]
    content_hashes = [image["content_hash"] for image in prepared_images]

    if len(image_ids) != len(set(image_ids)):
        raise ValueError("Duplicate image IDs are not allowed")

    if len(content_hashes) != len(set(content_hashes)):
        raise ValueError("Duplicate images are not allowed")

    s3 = ctx["s3"]
    session_factory = ctx["db_session_factory"]

    try:
        async with session_factory() as db:
            product = await ProductRepository(db).get_by_id(
                product_id=product_uuid,
            )
            image_repo = ProductImageRepository(db)
            existing_images = await image_repo.get_by_product_id(
                product_id=product_uuid,
            )

        if product is None:
            raise ValueError("Product not found")

        existing_by_id = {image.id: image for image in existing_images}

        new_image_count = sum(
            1 for image in prepared_images if image["image_id"] not in existing_by_id
        )

        if len(existing_images) + new_image_count > ProductImageConstants.MAX_IMAGES:
            raise ValueError("Maximum product image limit exceeded")

        processed_image_ids: list[str] = []

        for image in prepared_images:
            image_id = image["image_id"]
            final_key = image["final_key"]
            staging_key = image["staging_key"]
            content_hash = image["content_hash"]

            existing_image = existing_by_id.get(image_id)

            if existing_image is not None:
                if (
                    existing_image.product_id != product_uuid
                    or existing_image.object_key != final_key
                    or existing_image.content_hash != content_hash
                ):
                    raise ValueError("Existing image does not match job payload")

                saved_image = existing_image

            else:
                await s3.copy_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    CopySource={
                        "Bucket": settings.S3_BUCKET_NAME,
                        "Key": staging_key,
                    },
                    Key=final_key,
                    ContentType=image["content_type"],
                    MetadataDirective="REPLACE",
                )

                product_image = ProductImage(
                    id=image_id,
                    product_id=product_uuid,
                    object_key=final_key,
                    content_hash=content_hash,
                    is_primary=False,
                )

                try:
                    async with session_factory() as db:
                        async with db.begin():
                            saved_image = await ProductImageRepository(db).create(
                                product_image
                            )

                except IntegrityError as exc:
                    async with session_factory() as db:
                        saved_image = await ProductImageRepository(db).get_by_id(
                            image_id=image_id,
                        )

                    if (
                        saved_image is None
                        or saved_image.product_id != product_uuid
                        or saved_image.object_key != final_key
                        or saved_image.content_hash != content_hash
                    ):
                        await s3.delete_object(
                            Bucket=settings.S3_BUCKET_NAME,
                            Key=final_key,
                        )
                        raise ValueError(
                            "Product image conflicts with existing data"
                        ) from exc

                existing_by_id[image_id] = saved_image

            processed_image_ids.append(str(saved_image.id))

            await s3.delete_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=staging_key,
            )

        requested_primary_id = next(
            (image["image_id"] for image in prepared_images if image["is_primary"]),
            None,
        )

        async with session_factory() as db:
            async with db.begin():
                image_repo = ProductImageRepository(db)

                product_images = await image_repo.get_by_product_id(
                    product_id=product_uuid,
                )

                current_primary = next(
                    (image for image in product_images if image.is_primary),
                    None,
                )

                selected_primary_id = requested_primary_id

                if selected_primary_id is None and current_primary is not None:
                    selected_primary_id = current_primary.id

                if selected_primary_id is None and processed_image_ids:
                    selected_primary_id = UUID(processed_image_ids[0])

                if selected_primary_id is not None:
                    selected_image = next(
                        (
                            image
                            for image in product_images
                            if image.id == selected_primary_id
                        ),
                        None,
                    )

                    if selected_image is None:
                        raise ValueError("Primary image not found")

                    if (
                        current_primary is None
                        or current_primary.id != selected_image.id
                    ):
                        await image_repo.set_primary(
                            image=selected_image,
                        )

        return {
            "product_id": str(product_uuid),
            "uploaded": len(processed_image_ids),
            "image_ids": processed_image_ids,
        }

    except (
        BotoCoreError,
        ClientError,
        SQLAlchemyError,
    ) as exc:
        retry_delay = min(
            ctx.get("job_try", 1) * 10,
            60,
        )

        logger.exception("Background product-image upload failed")

        raise Retry(defer=retry_delay) from exc

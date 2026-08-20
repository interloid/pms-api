from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import get_product_image_service, get_current_user
from app.schemas.product_image_schema import ProductImageResponse
from app.services.product_image_service import ProductImageService

router = APIRouter(
    prefix="/products/{product_id}/images",
    tags=["Product Images"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_image(
    product_id: UUID,
    file: UploadFile = File(...),
    is_primary: bool = False,
    service: ProductImageService = Depends(get_product_image_service),
) -> ProductImageResponse:

    image = await service.upload_image(
        product_id=product_id,
        file=file.file,
        filename=file.filename or "image",
        content_type=file.content_type or "application/octet-stream",
        is_primary=is_primary,
    )

    return ProductImageResponse.model_validate(image)


@router.get("", response_model=list[ProductImageResponse])
async def get_product_images(
    product_id: UUID,
    service: ProductImageService = Depends(get_product_image_service),
) -> list[ProductImageResponse]:

    images = await service.get_product_images(product_id=product_id)

    return [ProductImageResponse.model_validate(image) for image in images]


@router.patch("/{image_id}/primary", response_model=ProductImageResponse)
async def set_primary_product_image(
    product_id: UUID,
    image_id: UUID,
    service: ProductImageService = Depends(get_product_image_service),
) -> ProductImageResponse:

    image = await service.set_primary_image(image_id=image_id, product_id=product_id)

    return ProductImageResponse.model_validate(image)


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_image(
    product_id: UUID,
    image_id: UUID,
    service: ProductImageService = Depends(get_product_image_service),
) -> None:

    await service.delete_image(image_id=image_id, product_id=product_id)

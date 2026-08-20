from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from io import BytesIO
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from app.models.category_model import Category
from app.models.product_model import Product
from app.schemas.product_schema import ProductCreate
from app.services.product_service import ProductService
from app.exceptions.custom import ConflictException, NotFoundException, BadRequestException
from app.core.constants import ProductStatusEnum, ProductImageConstants


#Create product successfully without images

@pytest.mark.asyncio
async def test_create_product_successfully():
    db = MagicMock()

    service = ProductService(db)

    category_id = uuid4()
    product_id = uuid4()

    category = Category(
        id=category_id,
        name="Electronics",
    )

    created_product = Product(
        id=product_id,
        name="iPhone 15",
        sku="IPHONE-15",
        category_id=category_id,
        price=Decimal("799.99"),
        stock=10,
        status=ProductStatusEnum.ACTIVE,
    )

    service._validate_product_images = AsyncMock()

    service.product_repo.get_by_sku = AsyncMock(
        return_value=None,
    )

    service.category_repo.get_by_name = AsyncMock(
        return_value=category,
    )

    service.product_repo.create = AsyncMock(
        return_value=created_product,
    )

    service.product_repo.get_by_id = AsyncMock(
        return_value=created_product,
    )

    payload = ProductCreate(
        name="iPhone 15",
        sku="IPHONE-15",
        category_name=" Electronics ",
        price=Decimal("799.99"),
        stock=10,
        status=ProductStatusEnum.ACTIVE,
    )

    result = await service.create_product(
        payload=payload,
        images=[],
    )

    assert result is created_product
    
    
#Duplicate SKU

@pytest.mark.asyncio
async def test_create_product_raises_conflict_for_duplicate_sku():
    db = MagicMock()

    service = ProductService(db)

    existing_product = Product(
        id=uuid4(),
        name="Existing Product",
        sku="IPHONE-15",
    )

    service._validate_product_images = AsyncMock()

    service.product_repo.get_by_sku = AsyncMock(
        return_value=existing_product,
    )

    service.category_repo.get_by_name = AsyncMock()

    service.product_repo.create = AsyncMock()

    payload = ProductCreate(
        name="New iPhone",
        sku="IPHONE-15",
        category_name="Electronics",
        price=Decimal("799.99"),
        stock=10,
        status=ProductStatusEnum.ACTIVE,
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.create_product(
            payload=payload,
            images=[],
        )

    assert str(exc_info.value) == (
        "Product with this SKU already exists"
    )

    service.product_repo.get_by_sku.assert_awaited_once_with(
        sku="IPHONE-15",
    )

    service.category_repo.get_by_name.assert_not_awaited()

    service.product_repo.create.assert_not_awaited()
    

#Category doesn't exist

@pytest.mark.asyncio
async def test_create_product_raises_not_found_when_category_does_not_exist():
    db = MagicMock()

    service = ProductService(db)

    service._validate_product_images = AsyncMock()

    service.product_repo.get_by_sku = AsyncMock(
        return_value=None,
    )

    service.category_repo.get_by_name = AsyncMock(
        return_value=None,
    )

    service.product_repo.create = AsyncMock()

    payload = ProductCreate(
        name="iPhone 15",
        sku="IPHONE-15",
        category_name="Unknown Category",
        price=Decimal("799.99"),
        stock=10,
        status=ProductStatusEnum.ACTIVE,
    )

    with pytest.raises(NotFoundException) as exc_info:
        await service.create_product(
            payload=payload,
            images=[],
        )

    assert str(exc_info.value) == "Category not found"

    service.category_repo.get_by_name.assert_awaited_once_with(
        name="Unknown Category",
    )

    service.product_repo.create.assert_not_awaited()
    
    
    
#IntegrityError during creation

@pytest.mark.asyncio
async def test_create_product_converts_integrity_error_to_conflict():
    db = MagicMock()
    db.rollback = AsyncMock()

    service = ProductService(db)

    category_id = uuid4()

    category = Category(
        id=category_id,
        name="Electronics",
    )

    service._validate_product_images = AsyncMock()

    service.product_repo.get_by_sku = AsyncMock(
        return_value=None,
    )

    service.category_repo.get_by_name = AsyncMock(
        return_value=category,
    )

    service.product_repo.create = AsyncMock(
        side_effect=IntegrityError(
            statement="INSERT INTO products",
            params={},
            orig=Exception("duplicate"),
        ),
    )

    payload = ProductCreate(
        name="iPhone 15",
        sku="IPHONE-15",
        category_name="Electronics",
        price=Decimal("799.99"),
        stock=10,
        status=ProductStatusEnum.ACTIVE,
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.create_product(
            payload=payload,
            images=[],
        )

    assert str(exc_info.value) == (
        "Product with this SKU already exists"
    )

    db.rollback.assert_awaited_once()
    
    
#Product creation with images    

image1 = UploadFile(
    filename="iphone-front.jpg",
    file=BytesIO(b"fake image 1"),
    headers={"content-type": "image/jpeg"},
)

image2 = UploadFile(
    filename="iphone-back.jpg",
    file=BytesIO(b"fake image 2"),
    headers={"content-type": "image/jpeg"},
)

images = [image1, image2]

@pytest.mark.asyncio
async def test_create_product_uploads_product_images():
    db = MagicMock()

    service = ProductService(db)

    category_id = uuid4()
    product_id = uuid4()

    category = Category(
        id=category_id,
        name="Electronics",
    )

    created_product = Product(
        id=product_id,
        name="iPhone 15",
        sku="IPHONE-15",
        category_id=category_id,
        price=Decimal("799.99"),
        stock=10,
        status=ProductStatusEnum.ACTIVE,
    )

    service._validate_product_images = AsyncMock()

    service.product_repo.get_by_sku = AsyncMock(
        return_value=None,
    )

    service.category_repo.get_by_name = AsyncMock(
        return_value=category,
    )

    service.product_repo.create = AsyncMock(
        return_value=created_product,
    )

    service.product_repo.get_by_id = AsyncMock(
        return_value=created_product,
    )

    service.product_image_service.upload_image = AsyncMock()

    image1 = UploadFile(
        filename="iphone-front.jpg",
        file=BytesIO(b"fake image 1"),
        headers={"content-type": "image/jpeg"},
    )

    image2 = UploadFile(
        filename="iphone-back.jpg",
        file=BytesIO(b"fake image 2"),
        headers={"content-type": "image/jpeg"},
    )

    images = [image1, image2]

    payload = ProductCreate(
        name="iPhone 15",
        sku="IPHONE-15",
        category_name="Electronics",
        price=Decimal("799.99"),
        stock=10,
        status=ProductStatusEnum.ACTIVE,
    )

    result = await service.create_product(
        payload=payload,
        images=images,
    )

    assert result is created_product

    assert service.product_image_service.upload_image.await_count == 2
    
    
#Product not found after creation

@pytest.mark.asyncio
async def test_create_product_raises_runtime_error_when_created_product_cannot_be_retrieved():
    db = MagicMock()

    service = ProductService(db)

    category_id = uuid4()
    product_id = uuid4()

    category = Category(
        id=category_id,
        name="Electronics",
    )

    created_product = Product(
        id=product_id,
        name="iPhone 15",
        sku="IPHONE-15",
        category_id=category_id,
    )

    service._validate_product_images = AsyncMock()

    service.product_repo.get_by_sku = AsyncMock(
        return_value=None,
    )

    service.category_repo.get_by_name = AsyncMock(
        return_value=category,
    )

    service.product_repo.create = AsyncMock(
        return_value=created_product,
    )

    service.product_repo.get_by_id = AsyncMock(
        return_value=None,
    )

    payload = ProductCreate(
        name="iPhone 15",
        sku="IPHONE-15",
        category_name="Electronics",
        price=Decimal("799.99"),
        stock=10,
        status=ProductStatusEnum.ACTIVE,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await service.create_product(
            payload=payload,
            images=[],
        )

    assert str(exc_info.value) == (
        "Product not found after creation"
    )
    
# Accepts valid images

@pytest.mark.asyncio
async def test_validate_product_images_accepts_valid_image():
    db = MagicMock()
    service = ProductService(db)
    
    image = UploadFile(
        filename='product.jpg',
        file=BytesIO(b"valid image"),
        headers={"content-type": "image/jpeg"},
    )
    
    result = await service._validate_product_images(images=[image])
    
    assert result is None


# Rejects too many images

@pytest.mark.asyncio
async def test_validate_product_images_rejects_too_many_images():
    db = MagicMock()
    service = ProductService(db)

    images = [
        UploadFile(
            filename=f"product-{index}.jpg",
            file=BytesIO(b"valid image"),
            headers={"content-type": "image/jpeg"},
        )
        for index in range(ProductImageConstants.MAX_IMAGES + 1)
    ]

    with pytest.raises(BadRequestException) as exc_info:
        await service._validate_product_images(
            images=images,
        )

    assert str(exc_info.value) == (
        f"Maximum {ProductImageConstants.MAX_IMAGES} images are allowed"
    )


# Rejects missing filename

@pytest.mark.asyncio
async def test_validate_product_images_rejects_missing_filename():
    db = MagicMock()
    service = ProductService(db)

    image = UploadFile(
        filename=None,
        file=BytesIO(b"valid image"),
        headers={"content-type": "image/jpeg"},
    )

    with pytest.raises(BadRequestException) as exc_info:
        await service._validate_product_images(
            images=[image],
        )

    assert str(exc_info.value) == "Image filename is required"


# Rejects missing content type

@pytest.mark.asyncio
async def test_validate_product_images_rejects_missing_content_type():
    db = MagicMock()
    service = ProductService(db)

    image = UploadFile(
        filename=f"product.jpg",
        file=BytesIO(b"valid image"),
    )

    with pytest.raises(BadRequestException) as exc_info:
        await service._validate_product_images(
            images=[image],
        )

    assert str(exc_info.value) == (
        "Content type could not be determined for 'product.jpg'"
    )


# Rejects unsupported content type

@pytest.mark.asyncio
async def test_validate_product_images_rejects_unsupported_content_type():
    db = MagicMock()
    service = ProductService(db)

    image = UploadFile(
        filename=f"product.jpg",
        file=BytesIO(b"valid image"),
        headers={"content-type": "application/pdf"},
    )

    with pytest.raises(BadRequestException) as exc_info:
        await service._validate_product_images(
            images=[image],
        )

    assert str(exc_info.value) == (
        "Unsupported image type 'application/pdf'. "
        "Allowed types: JPEG, PNG, and WebP"
    )

# Rejects file larger than 5 MB 

@pytest.mark.asyncio
async def test_validate_product_images_rejects_file_larger_than_maximum():
    db = MagicMock()
    service = ProductService(db)

    content = b"x" * (
        ProductImageConstants.MAX_FILE_SIZE + 1
    )

    image = UploadFile(
        filename="large-product.jpg",
        file=BytesIO(content),
        headers={"content-type": "image/jpeg"},
    )

    with pytest.raises(BadRequestException) as exc_info:
        await service._validate_product_images(
            images=[image],
        )

    assert str(exc_info.value) == (
        "Image 'large-product.jpg' exceeds the maximum size of 5 MB"
    )

 
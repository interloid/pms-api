from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.s3 import S3Service


def test_build_url_returns_s3_url():
    service = S3Service()

    service.bucket_name = "my-product-bucket"
    service.region = "ap-south-1"

    result = service.build_url(
        "products/123/images/image.jpg",
    )

    assert result == (
        "https://my-product-bucket.s3.ap-south-1.amazonaws.com/"
        "products/123/images/image.jpg"
    )
    
    
@pytest.mark.asyncio
async def test_upload_file_uploads_file_to_s3():
    service = S3Service()

    service.bucket_name = "my-product-bucket"
    service.region = "ap-south-1"
    service.access_key_id = "access-key"
    service.secret_access_key = "secret-key"

    file = BytesIO(b"fake image")
    object_key = "products/123/images/image.jpg"
    content_type = "image/jpeg"

    s3_client = MagicMock()
    s3_client.upload_fileobj = AsyncMock()

    client_context = MagicMock()
    client_context.__aenter__ = AsyncMock(
        return_value=s3_client,
    )
    client_context.__aexit__ = AsyncMock(
        return_value=None,
    )

    session = MagicMock()
    session.client.return_value = client_context

    with patch(
        "app.core.s3.aioboto3.Session",
        return_value=session,
    ):

        result = await service.upload_file(
            file=file,
            object_key=object_key,
            content_type=content_type,
        )

    assert result == service.build_url(object_key)

    session.client.assert_called_once_with(
        "s3",
        region_name="ap-south-1",
    )

    s3_client.upload_fileobj.assert_awaited_once_with(
        file,
        "my-product-bucket",
        object_key,
        ExtraArgs={
            "ContentType": "image/jpeg",
        },
    )
    
@pytest.mark.asyncio
async def test_delete_file_deletes_object_from_s3():
    service = S3Service()

    service.bucket_name = "my-product-bucket"
    service.region = "ap-south-1"
    service.access_key_id = "access-key"
    service.secret_access_key = "secret-key"

    object_key = "products/123/images/image.jpg"

    s3_client = MagicMock()
    s3_client.delete_object = AsyncMock()

    client_context = MagicMock()
    client_context.__aenter__ = AsyncMock(
        return_value=s3_client,
    )
    client_context.__aexit__ = AsyncMock(
        return_value=None,
    )

    session = MagicMock()
    session.client.return_value = client_context

    with patch(
        "app.core.s3.aioboto3.Session",
        return_value=session,
    ):

        result = await service.delete_file(
            object_key=object_key,
        )

    assert result is None

    session.client.assert_called_once_with(
        "s3",
        region_name="ap-south-1",
    )

    s3_client.delete_object.assert_awaited_once_with(
        Bucket="my-product-bucket",
        Key=object_key,
    )
    

@pytest.mark.asyncio
async def test_upload_file_propagates_s3_error():
    service = S3Service()

    service.bucket_name = "my-product-bucket"
    service.region = "ap-south-1"
    service.access_key_id = "access-key"
    service.secret_access_key = "secret-key"

    file = BytesIO(b"fake image")

    s3_client = MagicMock()
    s3_client.upload_fileobj = AsyncMock(
        side_effect=RuntimeError("S3 upload failed"),
    )

    client_context = MagicMock()
    client_context.__aenter__ = AsyncMock(
        return_value=s3_client,
    )
    client_context.__aexit__ = AsyncMock(
        return_value=None,
    )

    session = MagicMock()
    session.client.return_value = client_context

    with patch(
        "app.core.s3.aioboto3.Session",
        return_value=session,
    ):
        with pytest.raises(RuntimeError, match="S3 upload failed"):
            await service.upload_file(
                file=file,
                object_key="products/image.jpg",
                content_type="image/jpeg",
            )
            
        
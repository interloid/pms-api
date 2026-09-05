from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.s3 import S3Service


@pytest.mark.asyncio
async def test_generate_presigned_urls_returns_empty_mapping_without_client():
    client = MagicMock()
    service = S3Service(client=client)

    result = await service.generate_presigned_urls(object_keys=[])

    assert result == {}
    client.generate_presigned_url.assert_not_called()


@pytest.mark.asyncio
async def test_upload_file_uploads_file_to_s3():
    data = b"fake image"
    object_key = "products/123/images/image.jpg"
    content_type = "image/jpeg"

    s3_client = MagicMock()
    s3_client.put_object = AsyncMock()
    service = S3Service(client=s3_client)
    service.bucket_name = "my-product-bucket"

    result = await service.upload_file(
        data=data,
        object_key=object_key,
        content_type=content_type,
    )

    assert result is None

    s3_client.put_object.assert_awaited_once_with(
        Bucket="my-product-bucket",
        Key=object_key,
        Body=data,
        ContentType="image/jpeg",
    )


@pytest.mark.asyncio
async def test_generate_presigned_urls_uses_one_client_for_all_keys():
    object_keys = ["products/first.jpg", "products/second.jpg"]
    s3_client = MagicMock()
    s3_client.generate_presigned_url = AsyncMock(
        side_effect=[
            "https://signed.example/first.jpg",
            "https://signed.example/second.jpg",
        ]
    )
    service = S3Service(client=s3_client)
    service.bucket_name = "my-product-bucket"

    result = await service.generate_presigned_urls(
        object_keys=object_keys,
        expires_in=900,
    )

    assert result == {
        "products/first.jpg": "https://signed.example/first.jpg",
        "products/second.jpg": "https://signed.example/second.jpg",
    }
    assert s3_client.generate_presigned_url.await_count == 2
    s3_client.generate_presigned_url.assert_any_await(
        "get_object",
        Params={"Bucket": "my-product-bucket", "Key": "products/first.jpg"},
        ExpiresIn=900,
    )
    s3_client.generate_presigned_url.assert_any_await(
        "get_object",
        Params={"Bucket": "my-product-bucket", "Key": "products/second.jpg"},
        ExpiresIn=900,
    )


@pytest.mark.asyncio
async def test_delete_file_deletes_object_from_s3():
    object_key = "products/123/images/image.jpg"

    s3_client = MagicMock()
    s3_client.delete_object = AsyncMock()
    service = S3Service(client=s3_client)
    service.bucket_name = "my-product-bucket"

    result = await service.delete_file(
        object_key=object_key,
    )

    assert result is None

    s3_client.delete_object.assert_awaited_once_with(
        Bucket="my-product-bucket",
        Key=object_key,
    )


@pytest.mark.asyncio
async def test_upload_file_propagates_s3_error():
    data = b"fake image"

    s3_client = MagicMock()
    s3_client.put_object = AsyncMock(
        side_effect=RuntimeError("S3 upload failed"),
    )
    service = S3Service(client=s3_client)

    with pytest.raises(RuntimeError, match="S3 upload failed"):
        await service.upload_file(
            data=data,
            object_key="products/image.jpg",
            content_type="image/jpeg",
        )

from typing import Any

from fastapi import Request

from app.core.settings import settings


class S3Service:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.bucket_name = settings.S3_BUCKET_NAME

    async def upload_file(
        self, data: bytes, object_key: str, content_type: str
    ) -> None:
        print(repr(content_type), type(content_type))
        await self.client.put_object(
            Bucket=self.bucket_name,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )

    async def delete_file(self, object_key: str) -> None:

        await self.client.delete_object(
            Bucket=self.bucket_name,
            Key=object_key,
        )

    async def generate_presigned_urls(
        self, object_keys: list[str], expires_in: int = 3600
    ) -> dict[str, str]:
        if not object_keys:
            return {}

        presigned_urls: dict[str, str] = {}

        for object_key in object_keys:
            presigned_urls[object_key] = await self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expires_in,
            )

        return presigned_urls


def get_s3_service(request: Request) -> S3Service:
    return S3Service(client=request.app.state.s3)

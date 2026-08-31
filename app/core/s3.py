from typing import BinaryIO

import aioboto3

from app.core.settings import settings


class S3Service:
    def __init__(self) -> None:
        self.bucket_name = settings.S3_BUCKET_NAME
        self.region = settings.AWS_REGION
        self.access_key_id = settings.AWS_ACCESS_KEY_ID
        self.secret_access_key = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()

    async def upload_file(
        self, file: BinaryIO, object_key: str, content_type: str
    ) -> str:

        session = aioboto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )

        async with session.client("s3", region_name=self.region) as s3:
            await s3.upload_fileobj(
                file,
                self.bucket_name,
                object_key,
                ExtraArgs={
                    "ContentType": content_type,
                },
            )
        return self.build_url(object_key)

    async def delete_file(self, object_key: str) -> None:

        session = aioboto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )

        async with session.client("s3", region_name=self.region) as s3:
            await s3.delete_object(
                Bucket=self.bucket_name,
                Key=object_key,
            )

    def build_url(self, object_key: str) -> str:
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{object_key}"

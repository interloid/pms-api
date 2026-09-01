from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.s3 import S3Service
from app.core.security import decode_token, validate_access_token_payload
from app.db.session import get_db
from app.exceptions.custom import UnauthorizedException
from app.models.user_model import User
from app.repositories.product_image_repo import ProductImageRepository
from app.repositories.user_repo import UserRepository
from app.services.product_image_service import ProductImageService

bearer_schema = HTTPBearer(
    scheme_name="BearerAuth",
    description="Enter the JWT access token",
    auto_error=False,
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_schema),
    db: AsyncSession = Depends(get_db),
) -> User:

    if credentials is None:
        raise UnauthorizedException(message="Authentication required")

    if credentials.scheme.lower() != "bearer":
        raise UnauthorizedException(message="Invalid authentication scheme")

    try:
        decode_payload = decode_token(credentials.credentials)

        token_payload = validate_access_token_payload(decode_payload)

    except ExpiredSignatureError as exc:
        raise UnauthorizedException(message="Invalid access token") from exc

    except (ValidationError, ValueError, InvalidTokenError) as exc:
        raise UnauthorizedException(message="Invalid access token") from exc

    user = await UserRepository(db).get_by_id(token_payload.sub)

    if user is None or not user.is_active:
        raise UnauthorizedException(message="Invalid access token")

    return user


async def get_product_image_service(
    db: AsyncSession = Depends(get_db),
) -> ProductImageService:

    product_image_repo = ProductImageRepository(db=db)
    s3_service = S3Service()

    return ProductImageService(
        product_image_repo=product_image_repo,
        s3_service=s3_service,
    )

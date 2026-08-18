from uuid import UUID

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.s3 import S3Service
from app.db.redis import get_redis
from app.db.session import get_db
from app.exceptions.custom import UnauthorizedException
from app.repositories.product_image_repo import ProductImageRepository
from app.services.auth_service import AuthService
from app.services.product_image_service import ProductImageService

SESSION_COOKIE_NAME = "session_id"


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if not session_id:
        raise UnauthorizedException(
            message="Authentication required",
        )

    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise UnauthorizedException(
            message="Invalid session",
        )

    auth_service = AuthService(
        db=db,
        redis=redis,
    )

    return await auth_service.get_current_session(
        session_id=session_uuid,
    )


async def get_product_image_service(
    db: AsyncSession = Depends(get_db),
) -> ProductImageService:

    product_image_repo = ProductImageRepository(db=db)
    s3_service = S3Service()

    return ProductImageService(
        product_image_repo=product_image_repo,
        s3_service=s3_service,
    )

from uuid import UUID

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import get_db
from app.exceptions.custom import UnauthorizedException
from app.services.auth_service import AuthService

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

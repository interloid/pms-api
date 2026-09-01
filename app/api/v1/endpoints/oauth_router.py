from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.exceptions.custom import InternalServerException
from app.exceptions.global_exception import AUTH_ERROR_RESPONSES
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["OAUTH"],
)


def set_refresh_token_cookie(
    *,
    response: Response,
    raw_refresh_token: str,
    max_age: int,
) -> None:
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=max_age,
    )


@router.get(
    "/{provider}",
    responses=AUTH_ERROR_RESPONSES,
)
async def omniauth(
    provider: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    service = AuthService(
        db=db,
        redis=redis,
    )

    authorization_url = await service.start_oauth(
        provider=provider,
    )

    return RedirectResponse(
        url=authorization_url,
        status_code=302,
    )


@router.get(
    "/{provider}/callback",
    responses=AUTH_ERROR_RESPONSES,
)
async def omniauth_callback(
    provider: str,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    service = AuthService(
        db=db,
        redis=redis,
    )

    (
        result,
        raw_refresh_token,
        refresh_max_age,
    ) = await service.oauth_callback(
        provider=provider,
        code=code,
        state=state,
    )

    if result.data is None:
        raise InternalServerException(message="OAuth session data is missing")

    response = RedirectResponse(
        url=settings.YOUR_REACT_URL,
        status_code=302,
    )

    set_refresh_token_cookie(
        response=response,
        raw_refresh_token=raw_refresh_token,
        max_age=refresh_max_age,
    )

    return response

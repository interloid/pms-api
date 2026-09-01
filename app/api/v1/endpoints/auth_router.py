from fastapi import APIRouter, Cookie, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.settings import settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.exceptions.custom import InternalServerException
from app.exceptions.global_exception import AUTH_ERROR_RESPONSES
from app.models.user_model import User
from app.schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
    TokenResponse,
)
from app.schemas.response import ApiResponse
from app.schemas.user_schema import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["JWT Authentication"],
)


@router.post(
    "/login",
    response_model=ApiResponse[LoginResponse],
    responses=AUTH_ERROR_RESPONSES,
)
async def login(
    login_data: LoginRequest,
    response: Response,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db=db, redis=redis)

    (result, raw_refresh_token, refresh_max_age) = await service.login(login_data)

    if result.data is None:
        raise InternalServerException(
            message="Login response data is missing",
        )

    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=refresh_max_age,
    )

    return result


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    responses=AUTH_ERROR_RESPONSES,
)
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=settings.REFRESH_TOKEN_COOKIE_NAME,
    ),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    service = AuthService(
        db=db,
        redis=redis,
    )

    (
        result,
        new_raw_refresh_token,
        refresh_max_age,
    ) = await service.refresh_token(
        raw_refresh_token=refresh_token,
    )

    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=new_raw_refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )

    return result


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=AUTH_ERROR_RESPONSES,
)
async def logout_current_device(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=settings.REFRESH_TOKEN_COOKIE_NAME,
    ),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = AuthService(db=db, redis=redis)
    await service.logout_current_device(refresh_token)

    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
    )


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=AUTH_ERROR_RESPONSES,
)
async def logout_all_devices(
    response: Response,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = AuthService(db=db, redis=redis)
    await service.logout_all_devices(user_id=current_user.id)

    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    responses=AUTH_ERROR_RESPONSES,
)
async def get_current_user_details(
    current_user: User = Depends(get_current_user),
):
    return ApiResponse[UserResponse](
        message="Current user retrieved successfully",
        data=UserResponse(
            id=current_user.id,
            email=current_user.email,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            is_active=current_user.is_active,
            role=current_user.role,
        ),
    )

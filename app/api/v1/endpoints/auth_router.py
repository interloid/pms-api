from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
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
    PasscodeRequest,
    PasscodeVerifyRequest,
    TokenResponse,
)
from app.schemas.response import ApiResponse
from app.schemas.user_schema import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
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

    (result,raw_refresh_token,refresh_max_age) = await service.login(login_data)

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
            ),
    )


@router.post("/passcode/request")
async def request_passcode(
    request: Request,
    login_data: PasscodeRequest,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db=db, redis=redis)

    await service.request_passcode(
        email=login_data.email,
        client_ip=request.client.host or "unknown",
        redis=redis,
    )

    return ApiResponse(
        message="Verification code sent to the email is registered.",
    )


@router.post(
    "/passcode/verify",
    response_model=ApiResponse[LoginResponse],
    responses=AUTH_ERROR_RESPONSES
)
async def verify_passcode(
    login_data: PasscodeVerifyRequest,
    response: Response,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
)-> ApiResponse[LoginResponse]:
    
    service = AuthService(db=db, redis=redis)

    (result, raw_refresh_token, refresh_max_age) = await service.verify_email_passcode(
        email=login_data.email,
        passcode=login_data.passcode,
        redis=redis,
    )
    
    set_refresh_token_cookie(
        response=response,
        raw_refresh_token=raw_refresh_token,
        max_age=refresh_max_age,
    )

    return result

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

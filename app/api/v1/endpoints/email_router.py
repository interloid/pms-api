from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis

from app.api.dependencies import get_auth_service
from app.core.settings import settings
from app.db.redis import get_redis
from app.exceptions.global_exception import AUTH_ERROR_RESPONSES
from app.schemas.auth_schema import (
    LoginResponse,
    PasscodeRequest,
    PasscodeVerifyRequest,
)
from app.schemas.response import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Email Authentication"],
)


@router.post(
    "/passcode/request",
    response_model=ApiResponse[None],
    responses=AUTH_ERROR_RESPONSES,
)
async def request_passcode(
    request: Request,
    login_data: PasscodeRequest,
    redis: Redis = Depends(get_redis),
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[None]:
    await service.request_passcode(
        email=login_data.email,
        client_ip=request.client.host if request.client else "unknown",
        redis=redis,
    )

    return ApiResponse[None](
        message="Verification code sent to the email is registered.",
    )


@router.post(
    "/passcode/verifications",
    response_model=ApiResponse[LoginResponse],
    responses=AUTH_ERROR_RESPONSES,
)
async def verify_passcode(
    login_data: PasscodeVerifyRequest,
    response: Response,
    redis: Redis = Depends(get_redis),
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[LoginResponse]:

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

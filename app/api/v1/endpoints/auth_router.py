from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.exceptions.custom import (
    InternalServerException,
    UnauthorizedException,
)
from app.exceptions.global_exception import AUTH_ERROR_RESPONSES
from app.schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
    PasscodeRequest,
    PasscodeVerifyRequest,
)
from app.schemas.response import ApiResponse
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
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)

    result = await service.login(login_data)

    if result.data is None:
        raise InternalServerException(
            message="Login response data is missing",
        )

    if login_data.remember_me:
        max_age = settings.REMEMBER_ME_EXPIRE_DAYS * 24 * 60 * 60
    else:
        max_age = settings.SESSION_EXPIRE_DAYS * 24 * 60 * 60

    response.set_cookie(
        key="session",
        value=str(result.data.session_id),
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=max_age,
    )

    return result


@router.post("/logout")
async def logout(
    response: Response,
    session_id: str | None = Cookie(
        default=None,
        alias="session",
    ),
    db: AsyncSession = Depends(get_db),
):
    if session_id is not None:
        try:
            parsed_session_id = UUID(session_id)
        except ValueError:
            parsed_session_id = None

        if parsed_session_id is not None:
            service = AuthService(db)
            await service.logout(parsed_session_id)

    response.delete_cookie(
        key="session",
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
    )

    return ApiResponse(
        message="Logged out successfully",
    )


@router.get("/session")
async def session(
    session: str | None = Cookie(
        default=None,
        alias="session",
    ),
    db: AsyncSession = Depends(get_db),
):
    if session is None:
        raise UnauthorizedException(
            message="Session cookie is missing",
        )

    try:
        session_id = UUID(session)
    except ValueError as exc:
        raise UnauthorizedException(
            message="Invalid session",
        ) from exc

    service = AuthService(db)

    return await service.get_current_session(session_id)


@router.post("/passcode/request")
async def request_passcode(
    request: Request,
    login_data: PasscodeRequest,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)

    await service.request_passcode(
        email=login_data.email,
        client_ip=request.client.host,
        redis=redis,
    )

    return ApiResponse(
        message="Verification code sent to the email is registered.",
    )


@router.post("/passcode/verify")
async def verify_passcode(
    login_data: PasscodeVerifyRequest,
    response: Response,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)

    result = await service.verify_email_passcode(
        email=login_data.email,
        passcode=login_data.passcode,
        redis=redis,
    )

    if result.data is None:
        raise InternalServerException(
            message="Login response data is missing",
        )

    response.set_cookie(
        key="session",
        value=str(result.data.session_id),
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=settings.SESSION_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return result


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

    result = await service.oauth_callback(
        provider=provider,
        code=code,
        state=state,
    )

    if result.data is None:
        raise InternalServerException(message="OAuth session data is missing")

    session_id = result.data["session_id"]

    response = RedirectResponse(
        url=settings.YOUR_REACT_URL,
        status_code=302,
    )

    response.set_cookie(
        key="session",
        value=str(session_id),
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=settings.SESSION_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return response

from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Response, Request
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.core.oauth.client import get_oauth_client
from app.db.session import get_db
from app.core.settings import settings
from app.exceptions.custom import (
    InternalServerException,
    UnauthorizedException,
)
from app.exceptions.global_exception import AUTH_ERROR_RESPONSES
from app.schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
    PasscodeLoginRequest,
)
from app.schemas.response import ApiResponse
from app.services.auth_service import AuthService
from app.core.oauth.state import generate_oauth_state
from app.exceptions.custom import (
    AppException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)



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

    response.set_cookie(
        key="session",
        value=str(result.data.session_id),
        httponly=True,
        secure=True,
        samesite="lax",
    )

    return result


@router.post("/logout")
async def logout(
    response: Response,
    session_id: UUID | None = Cookie(
        default=None,
        alias="session",
    ),
    db: AsyncSession = Depends(get_db),
):
    if session_id is not None:
        service = AuthService(db)
        result = await service.logout(session_id)
    else:
        result = {
            "message": "Logged out successfully",
        }

    response.delete_cookie(
        key="session",
    )

    return result


@router.post("/session")
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


@router.post(
    "/login/passcode",
    response_model=ApiResponse[LoginResponse],
    responses=AUTH_ERROR_RESPONSES,
)
async def login_passcode(
    login_data: PasscodeLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)

    result = await service.login_passcode(login_data)

    if result.data is None:
        raise InternalServerException(
            message="Login response data is missing",
        )

    response.set_cookie(
        key="session",
        value=str(result.data.session_id),
        httponly=True,
        secure=True,
        samesite="lax",
    )

    return result

# @router.get(
#     "/omniauth/{provider}",
#     responses=AUTH_ERROR_RESPONSES,
# )
# async def omniauth(
#     provider: str,
#     db: AsyncSession = Depends(get_db),
#     redis: Redis = Depends(get_redis),
# ):

#     service = AuthService(
#         db=db,
#         redis=redis,
#     )

#     state = generate_oauth_state()

#     await service.oauth_state_repo.create(
#         state=state,
#         provider=provider,
#         ttl=settings.OAUTH_STATE_EXPIRE_SECONDS,
#     )

#     redirect_uri = settings.GOOGLE_REDIRECT_URI

#     return await oauth.google.authorize_redirect(
#         redirect_uri,
#         state=state,
#     )


@router.get(
    "/omniauth/{provider}",
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
    "/omniauth/{provider}/callback",
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
    
    session_id = result.data["session_id"]
    
    response = RedirectResponse(
        url=settings.YOUR_REACT_URL,
        status_code=302,
    )

    response.set_cookie(
        key="session",
        value=session_id,
        httponly=True,
    )

    return result


    
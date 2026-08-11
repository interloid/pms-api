from uuid import UUID

from fastapi import APIRouter, Depends, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
    PasscodeLoginRequest,
)
from app.services.auth_service import AuthService
from app.schemas.response import ApiResponse
from app.exceptions.custom import (
    UnauthorizedException,
    InternalServerException,
)
from app.exceptions.global_exception import AUTH_ERROR_RESPONSES

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login",
            response_model=ApiResponse[LoginResponse],
            responses=AUTH_ERROR_RESPONSES,
        )
async def login(
    login_data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    result =  await service.login(login_data)
    
    if result.data is None:
        raise InternalServerException(message="Login response data is missing")

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
    response: Response,
    session: str | None = Cookie(
        default=None,
    ),
    db: AsyncSession = Depends(get_db),
):
    if session is None:
        raise UnauthorizedException(message="Session cookie is missing")
        
    try:
        
        session_id = UUID(session)
        
    except ValueError as exc:
        raise UnauthorizedException(message="Invalid session") from exc

    service = AuthService(db)

    return await service.get_current_session(session_id)

@router.post(
    "/login/passcode",
    response_model=ApiResponse[LoginResponse],
)
async def login_passcode(
    login_data: PasscodeLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)

    result = await service.login_passcode(login_data)

    response.set_cookie(
        key="session",
        value=str(result.data.session_id),
        httponly=True,
        secure=True,
        samesite="lax",
    )

    return result

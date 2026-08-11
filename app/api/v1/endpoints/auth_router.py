from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth_schema import (
    LoginRequest,
    LogoutRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])



@router.post("/login")
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.login(login_data)


@router.post("/logout")
async def logout(
    logout_data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.logout(logout_data)



# from fastapi import APIRouter, Depends
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.db.session import get_db
# from app.models.user_model import User
# from app.schemas.response import ApiResponse
# from app.schemas.user_schema import UserResponse
# from app.services.user_service import UserService


# router = APIRouter(
#     prefix="/users",
#     tags=["Users"],
# )


# @router.get(
#     "/",
#     response_model=ApiResponse[list[UserResponse]],
# )
# async def get_users(
#     db: AsyncSession = Depends(get_db),
# ):
#     service = UserService(db)

#     return True #await service.get_users()


from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class UserBase(BaseSchema):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserResponse(UserBase):
    id: UUID
    first_name: str
    last_name: str
    is_active: bool


# class UserUpdate(BaseSchema):
#     name: str | None = Field(
#         default=None,
#         min_length=3,
#         max_length=50,
#     )
#     email: EmailStr | None = None

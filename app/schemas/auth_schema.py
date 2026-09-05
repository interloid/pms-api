from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema
from app.schemas.user_schema import UserResponse


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    remember_me: bool = False


class PasscodeRequest(BaseSchema):
    email: EmailStr


class LoginResponse(BaseSchema):
    access_token: str
    expires_in: int
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse


class PasscodeVerifyRequest(BaseSchema):
    email: EmailStr
    passcode: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )


class AccessTokenPayload(BaseSchema):
    sub: UUID
    type: Literal["access"]
    exp: int


class TokenResponse(BaseSchema):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0, description="Access token lifetime in seconds")

from uuid import UUID

from pydantic import EmailStr, Field

from app.core.constants import OAuthProviderEnum
from app.schemas.common import BaseSchema
from app.schemas.user_schema import UserResponse


class PasscodeLoginRequest(BaseSchema):
    passcode: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginResponse(BaseSchema):
    session_id: UUID
    user: UserResponse


class OAuthAuthorizationRequest(BaseSchema):
    provider: OAuthProviderEnum


class OAuthCallbackRequest(BaseSchema):
    provider: OAuthProviderEnum
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)


class OAuthUserInfo(BaseSchema):
    provider_id: str = Field(min_length=1)
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    email_verified: bool = False


# class OAuthLoginResponse(BaseSchema):
#     session_id: UUID
#     user: UserResponse

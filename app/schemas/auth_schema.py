from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class PasscodeLoginRequest(BaseSchema):
    passcode: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LogoutRequest(BaseSchema):
    refresh_token: str


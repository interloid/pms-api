from pydantic import EmailStr, Field
from uuid import UUID

from app.schemas.common import BaseSchema
from app.schemas.user_schema import UserResponse


class PasscodeLoginRequest(BaseSchema):
    passcode: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

class LoginResponse(BaseSchema):
    session_id: UUID
    user: UserResponse
    
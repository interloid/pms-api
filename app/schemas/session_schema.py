from datetime import datetime
from uuid import UUID

from app.schemas.common import BaseSchema
from app.schemas.user_schema import UserResponse


class SessionResponse(BaseSchema):
    user: UserResponse
    
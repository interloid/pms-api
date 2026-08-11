from uuid import UUID

from app.schemas.common import BaseSchema


class CategoryResponse(BaseSchema):
    id: UUID
    name: str
    

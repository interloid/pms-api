from uuid import UUID

from app.schemas.common import BaseSchema

class ProductImageResponse(BaseSchema):
    id: UUID
    url: str
    is_primary: bool
    
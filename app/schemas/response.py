from pydantic import Field

from app.schemas.common import BaseSchema


class ApiResponse[T](BaseSchema):
    success: bool = True
    message: str = Field(default="Success")
    data: T | None = None


class ErrorDetail(BaseSchema):
    code: str
    details: dict | None = None


class ErrorResponse(BaseSchema):
    success: bool = False
    message: str
    error: ErrorDetail
    request_id: str | None = None


class PaginationMeta(BaseSchema):
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedResponse[T](ApiResponse[list[T]]):
    pagination: PaginationMeta

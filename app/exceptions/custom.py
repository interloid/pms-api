from fastapi import status

from app.exceptions.base import AppException


class BadRequestException(AppException):
    def __init__(
        self,
        message: str = "Bad request",
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="BAD_REQUEST",
        )


class UnauthorizedException(AppException):
    def __init__(
        self,
        message: str = "Unauthorized",
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
        )


class ForbiddenException(AppException):
    def __init__(
        self,
        message: str = "Forbidden",
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
        )


class NotFoundException(AppException):
    def __init__(
        self,
        message: str = "Resource not found",
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
        )


class ConflictException(AppException):
    def __init__(
        self,
        message: str = "Conflict",
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT",
        )


class InternalServerException(AppException):
    def __init__(
        self,
        message: str = "Internal server error",
    ):
        super().__init__(
            status_code=500,
            message=message,
        )

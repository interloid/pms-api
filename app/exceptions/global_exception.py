from typing import Any

from app.schemas.response import ErrorResponse


AUTH_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {
        "model": ErrorResponse,
        "description": "Invalid credentials or session",
    },
    403: {
        "model": ErrorResponse,
        "description": "Access forbidden",
    },
    422: {
        "model": ErrorResponse,
        "description": "Validation error",
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal server error",
    },
}


CRUD_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "model": ErrorResponse,
        "description": "Bad request",
    },
    401: {
        "model": ErrorResponse,
        "description": "Authentication required",
    },
    403: {
        "model": ErrorResponse,
        "description": "Access forbidden",
    },
    404: {
        "model": ErrorResponse,
        "description": "Resource not found",
    },
    409: {
        "model": ErrorResponse,
        "description": "Resource conflict",
    },
    422: {
        "model": ErrorResponse,
        "description": "Validation error",
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal server error",
    },
}
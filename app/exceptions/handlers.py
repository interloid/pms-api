from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ExceptionHandler

from app.core.logging import get_logger
from app.exceptions.base import AppException
from app.schemas.response import ErrorDetail, ErrorResponse
from app.utils.helpers import request_id_ctx

logger = get_logger(__name__)


async def app_exception_handler(
    request: Request,
    exc: AppException,
):
    logger.warning(
        "%s | %s",
        exc.error_code,
        exc.message,
    )

    response = ErrorResponse(
        message=exc.message,
        error=ErrorDetail(
            code=exc.error_code,
            details=exc.details,
        ),
        request_id=request_id_ctx.get(),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
):
    logger.warning(
        "HTTP %s | %s",
        exc.status_code,
        exc.detail,
    )

    response = ErrorResponse(
        message=str(exc.detail),
        error=ErrorDetail(
            code="HTTP_EXCEPTION",
        ),
        request_id=request_id_ctx.get(),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    logger.warning(
        "Validation error | %s",
        exc.errors(),
    )

    errors = []

    for error in exc.errors():
        sanitized_error = {
            "type": error.get("type"),
            "loc": list(error.get("loc", [])),
            "msg": error.get("msg"),
        }

        if "input" in error:
            input_value = error["input"]

            if isinstance(input_value, (str, int, float, bool)) or input_value is None:
                sanitized_error["input"] = input_value
            else:
                sanitized_error["input"] = str(input_value)

        errors.append(sanitized_error)

    response = ErrorResponse(
        message="Validation failed",
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            details={
                "errors": errors,
            },
        ),
        request_id=request_id_ctx.get(),
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=response.model_dump(),
    )


async def general_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.exception(
        "Unhandled exception: %s",
        exc,
    )

    response = ErrorResponse(
        message="Internal server error",
        error=ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
        ),
        request_id=request_id_ctx.get(),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(),
    )


def register_exception_handlers(app: FastAPI):

    app.add_exception_handler(
        AppException,
        cast(ExceptionHandler, app_exception_handler),
    )

    app.add_exception_handler(
        HTTPException,
        cast(ExceptionHandler, http_exception_handler),
    )

    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_exception_handler),
    )

    app.add_exception_handler(
        Exception,
        general_exception_handler,
    )

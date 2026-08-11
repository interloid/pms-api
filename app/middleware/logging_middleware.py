import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger
from app.utils.helpers import (
    generate_request_id,
    method_ctx,
    path_ctx,
    request_id_ctx,
)

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        request_id = generate_request_id()

        request_id_token = request_id_ctx.set(request_id)
        method_token = method_ctx.set(request.method)
        path_token = path_ctx.set(request.url.path)

        start_time = time.perf_counter()

        try:
            logger.info("Request started")

            response = await call_next(request)

            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "Request completed | status_code=%s | duration=%.2f ms",
                response.status_code,
                duration_ms,
            )

            response.headers["X-Request-ID"] = request_id

            return response

        finally:
            request_id_ctx.reset(request_id_token)
            method_ctx.reset(method_token)
            path_ctx.reset(path_token)

from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def generate_request_id() -> str:
    return str(uuid4())


request_id_ctx: ContextVar[str] = ContextVar(
    "request_id",
    default="-",
)

method_ctx: ContextVar[str] = ContextVar(
    "method",
    default="-",
)

path_ctx: ContextVar[str] = ContextVar(
    "path",
    default="-",
)

import logging
import sys

from app.utils.helpers import (
    method_ctx,
    path_ctx,
    request_id_ctx,
)

LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)s | "
    "request_id=%(request_id)s | "
    "%(method)s | "
    "%(path)s | "
    "%(name)s | "
    "%(message)s "
)


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx.get("-")
        record.method = method_ctx.get("-")
        record.path = path_ctx.get("-")
        return True


def setup_logging():
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    stdout_handler = logging.StreamHandler(sys.stdout)

    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    root_logger.addHandler(stdout_handler)


def get_logger(name: str):
    return logging.getLogger(name)

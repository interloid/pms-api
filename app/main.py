from fastapi import FastAPI

from app.api.router import router as api_router
from app.core import config, lifespan
from app.core.logging import setup_logging
from app.exceptions.handlers import register_exception_handlers
from app.middleware.logging_middleware import LoggingMiddleware

setup_logging()

app = FastAPI(
    title=config.PROJECT_NAME,
    description=config.PROJECT_DESCRIPTION,
    version=config.VERSION,
    docs_url=config.DOCS_URL,
    redoc_url=config.REDOC_URL,
    lifespan=lifespan,
)
register_exception_handlers(app)

app.add_middleware(LoggingMiddleware)

app.include_router(api_router)

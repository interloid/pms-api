from sqlalchemy.ext.asyncio import create_async_engine

from app.core.settings import settings

engine = create_async_engine(
    settings.DATABASE_URL.get_secret_value(),
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
)

from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.db.database import engine
from app.exceptions.custom import ServiceUnavailableException

logger = get_logger(__name__)

SessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with SessionLocal() as db:
        try:
            yield db
            await db.commit()
        except SQLAlchemyTimeoutError as exc:
            await db.rollback()
            logger.error(
                "Database connection pool exhausted | error=%s",
                exc,
            )
            raise ServiceUnavailableException(
                message="Database temporarily unavailable",
            ) from exc
        except Exception:
            await db.rollback()
            raise

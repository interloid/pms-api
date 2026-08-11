from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.database import engine

SessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with SessionLocal() as db:
        yield db

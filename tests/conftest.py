from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)


@pytest_asyncio.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    database_url = "postgresql+asyncpg://postgres:test@localhost:8080/postgres"

    if not database_url:
        raise RuntimeError("Database url is missing")

    parsed_url = make_url(database_url)

    if parsed_url.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Tests must use the local PostgreSQL database")

    engine = create_async_engine(database_url, pool_pre_ping=True)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def test_db_connection(
    test_engine: AsyncEngine,
) -> AsyncIterator[AsyncConnection]:
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            if transaction.is_active:
                await transaction.rollback()


@pytest_asyncio.fixture
async def db_session(
    test_db_connection: AsyncConnection,
) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(
        bind=test_db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..settings import settings

# The database_url from settings is already the full async-driver DSN
# (e.g. sqlite+aiosqlite:// or postgresql+asyncpg://) — the auto-derive
# validator in DatabaseSettings writes the driver prefix directly.
# Keep the remapping table for any manually configured URLs that still use
# the plain driver name (e.g. DATABASE_URL=sqlite:///... in a .env file).
engine_mappings = {
    "sqlite://": "sqlite+aiosqlite://",
    "postgresql://": "postgresql+asyncpg://",
}

db_url: str = settings.database_url  # type: ignore[assignment]  # always str after model_validator
for find, replace in engine_mappings.items():
    if db_url.startswith(find):
        db_url = replace + db_url[len(find) :]
        break


engine = create_async_engine(db_url, future=True, echo=settings.debug)


@event.listens_for(engine.sync_engine, "connect")
def _set_wal_mode(dbapi_conn: Any, _connection_record: Any) -> None:
    """Enable WAL journal mode on every new SQLite connection.

    WAL allows concurrent reads alongside the single writer so that
    mid-adventure checkpoint writes don't block reads elsewhere in the session.
    This listener is a no-op for PostgreSQL connections.
    """
    if "sqlite" in db_url:
        dbapi_conn.execute("PRAGMA journal_mode=WAL")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


async def get_session_depends() -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session


async def test_data(session: AsyncSession) -> None:
    """Populate the test database with initial data."""
    if os.environ.get("IS_DEV", "") != "":
        raise ValueError("This function should not be called in production. Enable IS_DEV to run it in development.")

    # Example: Add initial data to the session
    # await session.add_all([YourModel(name="Test")])
    # await session.commit()

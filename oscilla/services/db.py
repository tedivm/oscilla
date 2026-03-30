import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from typing import Any, AsyncGenerator

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ..settings import settings

logger = getLogger(__name__)

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


def migrate_database() -> bool:
    """Apply any pending Alembic migrations to the database.

    If the database is a local SQLite file and migrations are pending, a
    timestamped backup copy is created before the upgrade runs so that the
    original data can be restored if something goes wrong.

    Returns True if migrations were applied, False if the database was already
    up to date.

    Uses the same sync driver logic as ``db/env.py`` so that Alembic's
    programmatic API works correctly.
    """
    # Derive the synchronous URL from the async URL in settings.
    _async_to_sync = {
        "sqlite+aiosqlite://": "sqlite:///",
        "postgresql+asyncpg://": "postgresql://",
    }
    sync_url: str = settings.database_url  # type: ignore[assignment]
    for async_prefix, sync_prefix in _async_to_sync.items():
        if sync_url.startswith(async_prefix):
            sync_url = sync_prefix + sync_url[len(async_prefix) :]
            break

    # Check whether any migrations are pending before doing anything else.
    check_engine = create_engine(sync_url, poolclass=NullPool)
    try:
        with check_engine.connect() as conn:
            migration_ctx = MigrationContext.configure(conn)
            current_rev = migration_ctx.get_current_revision()
    finally:
        check_engine.dispose()

    # Load Alembic config to find the head revision.
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    if current_rev == head_rev:
        logger.debug("Database schema is up to date (revision %s).", current_rev)
        return False

    logger.info(
        "Database schema needs migration: current=%s head=%s.",
        current_rev,
        head_rev,
    )

    # Back up the database file if it is a local SQLite file.
    if sync_url.startswith("sqlite:///"):
        db_path_str = sync_url[len("sqlite:///") :]
        db_path = Path(db_path_str)
        if db_path.exists():
            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = db_path.with_suffix(f".bak.{timestamp}")
            shutil.copy2(db_path, backup_path)
            logger.info("Database backed up to %s before migration.", backup_path)

    # Run the upgrade.
    command.upgrade(alembic_cfg, "head")
    logger.info("Database migration complete (now at revision %s).", head_rev)
    return True

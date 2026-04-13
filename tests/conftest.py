from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import all ORM models so that Base.metadata.create_all() sees every table.
import oscilla.models  # noqa: F401
from oscilla.models.base import Base
from oscilla.services.cache import configure_caches
from oscilla.services.db import get_session_depends, test_data
from oscilla.www import app


@pytest.fixture(autouse=True)
def _configure_caches() -> None:
    """Ensure aiocache is configured before every test.

    TestClient does not automatically trigger the FastAPI lifespan, so caches
    must be configured explicitly.  Individual test modules may override this
    behavior with their own autouse fixtures (e.g. to force NoOpCache).
    """
    configure_caches()


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an AsyncSession backed by a fresh in-memory SQLite database.

    All ORM tables are created before each test and disposed afterwards.
    Use this fixture for service-layer unit tests that need a DB but should
    not touch the filesystem or real migrations.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_maker(tmpdir: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Creates a test database engine, complete with fake data."""
    test_database_url = f"sqlite+aiosqlite:///{tmpdir}/test_database.db"  # Use SQLite for testing; adjust as needed
    engine = create_async_engine(test_database_url, future=True, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_maker() as session:
        await test_data(session)

    yield async_session_maker

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_session_maker: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def fastapi_client(db_session_maker: async_sessionmaker[AsyncSession]) -> AsyncGenerator[TestClient, None]:
    """Fixture to create a FastAPI test client."""
    client = TestClient(app)

    async def get_session_depends_override() -> AsyncGenerator[AsyncSession, None]:
        async with db_session_maker() as session:
            yield session

    app.dependency_overrides[get_session_depends] = get_session_depends_override
    yield client


@pytest_asyncio.fixture
async def auth_client(
    db_session_maker: async_sessionmaker[AsyncSession], monkeypatch: Any
) -> AsyncGenerator[TestClient, None]:
    """FastAPI TestClient with:
    - test database session injected via dependency override
    - ``oscilla.services.email.send_email`` patched to a no-op async coroutine

    The patched send_email records calls in ``auth_client.sent_emails`` for
    assertions.
    """
    sent_emails: List[Dict[str, Any]] = []

    async def fake_send_email(to: str, subject: str, body_html: str, body_text: str) -> None:
        sent_emails.append({"to": to, "subject": subject, "body_html": body_html, "body_text": body_text})

    # auth.py imports send_email at module level, so we must patch the reference
    # in oscilla.services.auth rather than the source module.
    monkeypatch.setattr("oscilla.services.auth.send_email", fake_send_email)

    client = TestClient(app)
    client.sent_emails = sent_emails  # type: ignore[attr-defined]

    async def get_session_depends_override() -> AsyncGenerator[AsyncSession, None]:
        async with db_session_maker() as session:
            yield session

    app.dependency_overrides[get_session_depends] = get_session_depends_override
    yield client
    app.dependency_overrides.pop(get_session_depends, None)

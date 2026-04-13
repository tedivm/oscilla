"""Tests for the health and readiness endpoints."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from oscilla.services.db import get_session_depends
from oscilla.www import app


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client; uses the real DB via conftest db_session_maker."""
    return TestClient(app)


def test_health_always_200(client: TestClient) -> None:
    """GET /health returns 200 with status ok regardless of dependencies."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_200_with_live_db(auth_client: TestClient) -> None:
    """GET /ready with the test DB fixture returns 200 and db: true."""
    response = auth_client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["db"] is True
    assert body["status"] == "ok"


def test_ready_503_with_dead_db(monkeypatch: Any) -> None:
    """GET /ready with a broken DB returns 503 and db: false."""

    async def bad_execute(*args: Any, **kwargs: Any) -> None:
        raise SQLAlchemyError("Simulated DB failure")

    async def broken_session_dep() -> Any:
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(side_effect=bad_execute)
        yield session

    app.dependency_overrides[get_session_depends] = broken_session_dep
    try:
        with TestClient(app) as c:
            response = c.get("/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["db"] is False
        assert body["status"] == "degraded"
    finally:
        app.dependency_overrides.pop(get_session_depends, None)

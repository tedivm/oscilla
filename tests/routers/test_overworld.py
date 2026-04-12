"""Integration tests for the overworld router (location navigation and state)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import oscilla.models  # noqa: F401  — registers all ORM tables with Base.metadata
from oscilla.engine.loader import load_from_disk
from oscilla.engine.registry import ContentRegistry
from oscilla.models.base import Base
from oscilla.services.db import get_session_depends
from oscilla.www import app

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ow_registry() -> ContentRegistry:
    registry, _warnings = load_from_disk(FIXTURES / "play-api")
    return registry


@pytest_asyncio.fixture
async def ow_db_maker(tmp_path: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    db_url = f"sqlite+aiosqlite:///{tmp_path}/ow_test.db"
    engine = create_async_engine(db_url, future=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def ow_client(
    ow_db_maker: async_sessionmaker[AsyncSession],
    ow_registry: ContentRegistry,
) -> AsyncGenerator[TestClient, None]:
    """TestClient with play-api registry, in-memory DB, and patched email."""

    async def override() -> AsyncGenerator[AsyncSession, None]:
        async with ow_db_maker() as session:
            yield session

    app.dependency_overrides[get_session_depends] = override
    app.state.registries = {"test-play-game": ow_registry}
    with patch("oscilla.services.auth.send_email", new_callable=AsyncMock):
        client = TestClient(app)
        yield client
    app.dependency_overrides.pop(get_session_depends, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register(client: TestClient, email: str, password: str = "testpass123") -> None:
    client.post("/auth/register", json={"email": email, "password": password})


def _login(client: TestClient, email: str, password: str = "testpass123") -> Dict[str, str]:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_character(client: TestClient, headers: Dict[str, str], game: str = "test-play-game") -> Dict[str, Any]:
    resp = client.post("/characters", json={"game_name": game}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _navigate(client: TestClient, char_id: str, location_ref: str, headers: Dict[str, str]) -> Dict[str, Any]:
    resp = client.post(f"/characters/{char_id}/navigate", json={"location_ref": location_ref}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# GET /overworld
# ---------------------------------------------------------------------------


def test_get_overworld_fresh_character_has_null_location(ow_client: TestClient) -> None:
    """A fresh character has no current location."""
    _register(ow_client, "ow-get-fresh@x.com")
    h = _login(ow_client, "ow-get-fresh@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.get(f"/characters/{char['id']}/overworld", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["character_id"] == char["id"]
    assert body["current_location"] is None
    assert body["current_location_name"] is None
    assert body["current_region_name"] is None
    assert body["available_adventures"] == []
    assert body["navigation_options"] == []


def test_get_overworld_returns_location_after_navigate(ow_client: TestClient) -> None:
    """After navigation, GET /overworld reflects the new location."""
    _register(ow_client, "ow-get-nav@x.com")
    h = _login(ow_client, "ow-get-nav@x.com")
    char = _create_character(ow_client, h)

    _navigate(ow_client, char["id"], "test-location", h)

    resp = ow_client.get(f"/characters/{char['id']}/overworld", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_location"] == "test-location"
    assert body["current_location_name"] == "Test Location"
    assert body["current_region_name"] is not None
    # Should include both test adventures
    adventure_refs = [a["ref"] for a in body["available_adventures"]]
    assert "test-narrative" in adventure_refs
    assert "test-choice" in adventure_refs
    # Navigation options must include both locations in the region
    nav_refs = [n["ref"] for n in body["navigation_options"]]
    assert "test-location" in nav_refs
    assert "test-location-secondary" in nav_refs


def test_get_overworld_marks_current_location_is_current(ow_client: TestClient) -> None:
    """The current location has is_current=True in navigation_options."""
    _register(ow_client, "ow-get-iscurrent@x.com")
    h = _login(ow_client, "ow-get-iscurrent@x.com")
    char = _create_character(ow_client, h)

    _navigate(ow_client, char["id"], "test-location", h)

    resp = ow_client.get(f"/characters/{char['id']}/overworld", headers=h)
    assert resp.status_code == 200
    nav_opts = resp.json()["navigation_options"]
    current_opts = [n for n in nav_opts if n["ref"] == "test-location"]
    assert len(current_opts) == 1
    assert current_opts[0]["is_current"] is True


def test_get_overworld_returns_404_for_other_users_character(ow_client: TestClient) -> None:
    _register(ow_client, "ow-get-owner@x.com")
    _register(ow_client, "ow-get-other@x.com")
    owner_h = _login(ow_client, "ow-get-owner@x.com")
    other_h = _login(ow_client, "ow-get-other@x.com")
    char = _create_character(ow_client, owner_h)

    resp = ow_client.get(f"/characters/{char['id']}/overworld", headers=other_h)
    assert resp.status_code == 404


def test_get_overworld_returns_401_when_unauthenticated(ow_client: TestClient) -> None:
    _register(ow_client, "ow-get-noauth@x.com")
    h = _login(ow_client, "ow-get-noauth@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.get(f"/characters/{char['id']}/overworld")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /navigate
# ---------------------------------------------------------------------------


def test_navigate_updates_location_and_returns_overworld_state(ow_client: TestClient) -> None:
    """Navigate to a valid location and verify the response reflects the new state."""
    _register(ow_client, "ow-nav-ok@x.com")
    h = _login(ow_client, "ow-nav-ok@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.post(f"/characters/{char['id']}/navigate", json={"location_ref": "test-location"}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_location"] == "test-location"
    assert body["current_location_name"] == "Test Location"


def test_navigate_to_secondary_location(ow_client: TestClient) -> None:
    """Navigate to the secondary location — should have no adventures."""
    _register(ow_client, "ow-nav-secondary@x.com")
    h = _login(ow_client, "ow-nav-secondary@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.post(
        f"/characters/{char['id']}/navigate",
        json={"location_ref": "test-location-secondary"},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_location"] == "test-location-secondary"
    assert body["available_adventures"] == []


def test_navigate_persists_location(ow_client: TestClient) -> None:
    """After navigate, GET /overworld shows the updated location."""
    _register(ow_client, "ow-nav-persist@x.com")
    h = _login(ow_client, "ow-nav-persist@x.com")
    char = _create_character(ow_client, h)

    ow_client.post(f"/characters/{char['id']}/navigate", json={"location_ref": "test-location"}, headers=h)

    resp = ow_client.get(f"/characters/{char['id']}/overworld", headers=h)
    assert resp.status_code == 200
    assert resp.json()["current_location"] == "test-location"


def test_navigate_with_unknown_location_returns_422(ow_client: TestClient) -> None:
    _register(ow_client, "ow-nav-bad@x.com")
    h = _login(ow_client, "ow-nav-bad@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.post(
        f"/characters/{char['id']}/navigate",
        json={"location_ref": "nonexistent-location"},
        headers=h,
    )
    assert resp.status_code == 422


def test_navigate_returns_404_for_other_users_character(ow_client: TestClient) -> None:
    _register(ow_client, "ow-nav-owner@x.com")
    _register(ow_client, "ow-nav-other@x.com")
    owner_h = _login(ow_client, "ow-nav-owner@x.com")
    other_h = _login(ow_client, "ow-nav-other@x.com")
    char = _create_character(ow_client, owner_h)

    resp = ow_client.post(
        f"/characters/{char['id']}/navigate",
        json={"location_ref": "test-location"},
        headers=other_h,
    )
    assert resp.status_code == 404


def test_navigate_returns_401_when_unauthenticated(ow_client: TestClient) -> None:
    _register(ow_client, "ow-nav-noauth@x.com")
    h = _login(ow_client, "ow-nav-noauth@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.post(
        f"/characters/{char['id']}/navigate",
        json={"location_ref": "test-location"},
    )
    assert resp.status_code == 401

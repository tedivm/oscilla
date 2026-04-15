"""Integration tests for the overworld router (GET /overworld)."""

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


def _register(client: TestClient, email: str, password: str = "securepass123") -> None:
    client.post("/api/auth/register", json={"email": email, "password": password})


def _login(client: TestClient, email: str, password: str = "securepass123") -> Dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_character(client: TestClient, headers: Dict[str, str], game: str = "test-play-game") -> Dict[str, Any]:
    resp = client.post("/api/characters", json={"game_name": game}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# GET /overworld — shape and content
# ---------------------------------------------------------------------------


def test_get_overworld_returns_correct_top_level_shape(ow_client: TestClient) -> None:
    """GET /overworld returns character_id, accessible_locations, and region_graph."""
    _register(ow_client, "ow-shape@x.com")
    h = _login(ow_client, "ow-shape@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.get(f"/api/characters/{char['id']}/overworld", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["character_id"] == char["id"]
    assert "accessible_locations" in body
    assert "region_graph" in body
    # Old fields must not appear
    assert "current_location" not in body
    assert "available_adventures" not in body
    assert "navigation_options" not in body


def test_get_overworld_accessible_locations_non_empty(ow_client: TestClient) -> None:
    """accessible_locations includes all locations with no unlock conditions."""
    _register(ow_client, "ow-locs@x.com")
    h = _login(ow_client, "ow-locs@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.get(f"/api/characters/{char['id']}/overworld", headers=h)
    assert resp.status_code == 200
    locs = resp.json()["accessible_locations"]
    assert len(locs) >= 1
    # All locations in play-api have no unlock conditions, so all should appear
    refs = [loc["ref"] for loc in locs]
    assert "test-location" in refs
    assert "test-location-secondary" in refs


def test_get_overworld_location_option_shape(ow_client: TestClient) -> None:
    """Each LocationOptionRead has ref, display_name, region_ref, region_name, adventures_available."""
    _register(ow_client, "ow-locshape@x.com")
    h = _login(ow_client, "ow-locshape@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.get(f"/api/characters/{char['id']}/overworld", headers=h)
    assert resp.status_code == 200
    locs = resp.json()["accessible_locations"]
    for loc in locs:
        assert "ref" in loc
        assert "display_name" in loc
        assert "region_ref" in loc
        assert "region_name" in loc
        assert "adventures_available" in loc
        # Old field must not appear
        assert "is_current" not in loc


def test_get_overworld_adventures_available_is_true_for_location_with_adventures(ow_client: TestClient) -> None:
    """adventures_available is True for test-location (has 2 adventures) and False for secondary."""
    _register(ow_client, "ow-advavail@x.com")
    h = _login(ow_client, "ow-advavail@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.get(f"/api/characters/{char['id']}/overworld", headers=h)
    assert resp.status_code == 200
    locs = {loc["ref"]: loc for loc in resp.json()["accessible_locations"]}

    # test-location has test-narrative and test-choice — both are eligible for a fresh character
    assert locs["test-location"]["adventures_available"] is True
    # test-location-secondary has no adventures
    assert locs["test-location-secondary"]["adventures_available"] is False


def test_get_overworld_region_graph_has_nodes_and_edges(ow_client: TestClient) -> None:
    """region_graph contains at least one node (the root region) and edges list."""
    _register(ow_client, "ow-graph@x.com")
    h = _login(ow_client, "ow-graph@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.get(f"/api/characters/{char['id']}/overworld", headers=h)
    assert resp.status_code == 200
    graph = resp.json()["region_graph"]
    assert "nodes" in graph
    assert "edges" in graph
    assert isinstance(graph["nodes"], list)
    assert isinstance(graph["edges"], list)
    # play-api has one root region and two locations → at least 3 nodes
    assert len(graph["nodes"]) >= 1
    # Verify at least one node has the region in its id
    node_ids = [n["id"] for n in graph["nodes"]]
    assert any("test-region-root" in nid for nid in node_ids)


# ---------------------------------------------------------------------------
# GET /overworld — auth and ownership
# ---------------------------------------------------------------------------


def test_get_overworld_returns_404_for_other_users_character(ow_client: TestClient) -> None:
    _register(ow_client, "ow-get-owner@x.com")
    _register(ow_client, "ow-get-other@x.com")
    owner_h = _login(ow_client, "ow-get-owner@x.com")
    other_h = _login(ow_client, "ow-get-other@x.com")
    char = _create_character(ow_client, owner_h)

    resp = ow_client.get(f"/api/characters/{char['id']}/overworld", headers=other_h)
    assert resp.status_code == 404


def test_get_overworld_returns_401_when_unauthenticated(ow_client: TestClient) -> None:
    _register(ow_client, "ow-get-noauth@x.com")
    h = _login(ow_client, "ow-get-noauth@x.com")
    char = _create_character(ow_client, h)

    resp = ow_client.get(f"/api/characters/{char['id']}/overworld")
    assert resp.status_code == 401

"""Integration tests for the /characters router."""

from typing import Any, Dict
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from oscilla.engine.models.character_config import CharacterConfigManifest
from oscilla.engine.models.game import GameManifest
from oscilla.engine.models.time import GameTimeSpec
from oscilla.engine.registry import ContentRegistry
from oscilla.www import app


@pytest.fixture
def characters_client(auth_client: TestClient) -> TestClient:
    """Auth-enabled client with in-memory registries configured for character tests."""
    app.state.registries = {
        "test-alpha": _build_registry(name="test-alpha", display_name="Test Alpha", with_time=False),
        "test-beta": _build_registry(name="test-beta", display_name="Test Beta", with_time=True),
    }
    return auth_client


def _build_registry(name: str, display_name: str, with_time: bool) -> ContentRegistry:
    registry = ContentRegistry()
    game_spec: Dict[str, Any] = {
        "displayName": display_name,
        "description": f"Description for {display_name}",
    }
    if with_time:
        game_spec["time"] = GameTimeSpec().model_dump()

    registry.game = GameManifest.model_validate(
        {
            "apiVersion": "oscilla/v1",
            "kind": "Game",
            "metadata": {"name": name},
            "spec": game_spec,
        }
    )
    registry.character_config = CharacterConfigManifest.model_validate(
        {
            "apiVersion": "oscilla/v1",
            "kind": "CharacterConfig",
            "metadata": {"name": f"{name}-character-config"},
            "spec": {
                "public_stats": [
                    {"name": "health", "type": "int", "default": 10, "description": "Health"},
                    {"name": "is_blessed", "type": "bool", "default": False, "description": "Blessed"},
                ],
                "hidden_stats": [
                    {"name": "power", "type": "int", "derived": "{{ stats.health }}", "description": "Power"},
                ],
            },
        }
    )
    return registry


def _auth_headers(client: TestClient, email: str, password: str = "securepass123") -> Dict[str, str]:
    client.post("/api/auth/register", json={"email": email, "password": password})
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    body = login.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _create_character(client: TestClient, headers: Dict[str, str], game_name: str = "test-alpha") -> Dict[str, Any]:
    response = client.post("/api/characters", json={"game_name": game_name}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_post_characters_creates_character(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-create@example.com")

    response = characters_client.post("/api/characters", json={"game_name": "test-alpha"}, headers=headers)
    assert response.status_code == 201

    body = response.json()
    assert UUID(body["id"])
    assert body["game_name"] == "test-alpha"
    assert body["prestige_count"] == 0


def test_post_characters_rejects_unknown_game(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-badgame@example.com")

    response = characters_client.post("/api/characters", json={"game_name": "unknown-game"}, headers=headers)
    assert response.status_code == 422


def test_post_characters_duplicate_returns_409(characters_client: TestClient) -> None:
    """Creating a second character with the same name for the same game returns 409."""
    headers = _auth_headers(characters_client, "char-duplicate@example.com")

    first = characters_client.post("/api/characters", json={"game_name": "test-alpha"}, headers=headers)
    assert first.status_code == 201

    second = characters_client.post("/api/characters", json={"game_name": "test-alpha"}, headers=headers)
    assert second.status_code == 409


def test_post_characters_requires_authentication(characters_client: TestClient) -> None:
    response = characters_client.post("/api/characters", json={"game_name": "test-alpha"})
    assert response.status_code == 401


def test_get_characters_returns_only_authenticated_users_characters(characters_client: TestClient) -> None:
    user1_headers = _auth_headers(characters_client, "char-list-user1@example.com")
    user2_headers = _auth_headers(characters_client, "char-list-user2@example.com")

    _create_character(characters_client, headers=user1_headers, game_name="test-alpha")
    _create_character(characters_client, headers=user2_headers, game_name="test-alpha")

    response = characters_client.get("/api/characters", headers=user1_headers)
    assert response.status_code == 200

    body = response.json()
    assert len(body) == 1
    assert body[0]["game_name"] == "test-alpha"


def test_get_characters_filters_by_game_query_param(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-filter@example.com")

    _create_character(characters_client, headers=headers, game_name="test-alpha")
    _create_character(characters_client, headers=headers, game_name="test-beta")

    response = characters_client.get("/api/characters?game=test-beta", headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert len(body) == 1
    assert body[0]["game_name"] == "test-beta"


def test_get_characters_returns_empty_when_user_has_none(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-empty@example.com")

    response = characters_client.get("/api/characters", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_character_by_id_returns_full_state(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-full@example.com")
    created = _create_character(characters_client, headers=headers, game_name="test-alpha")

    response = characters_client.get(f"/api/characters/{created['id']}", headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == created["id"]
    assert body["game_name"] == "test-alpha"
    assert isinstance(body["stats"], dict)
    assert isinstance(body["stacks"], dict)
    assert isinstance(body["instances"], list)
    assert isinstance(body["equipment"], dict)


def test_character_state_stats_include_declared_and_unset(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-stats@example.com")
    created = _create_character(characters_client, headers=headers, game_name="test-alpha")

    response = characters_client.get(f"/api/characters/{created['id']}", headers=headers)
    assert response.status_code == 200
    stats = response.json()["stats"]

    assert "health" in stats
    assert "is_blessed" in stats
    assert "power" in stats

    assert stats["health"]["value"] == 10
    assert stats["is_blessed"]["value"] is False
    assert stats["power"]["value"] is None


def test_get_character_by_id_returns_404_for_other_users_character(characters_client: TestClient) -> None:
    owner_headers = _auth_headers(characters_client, "char-owner@example.com")
    other_headers = _auth_headers(characters_client, "char-other@example.com")

    created = _create_character(characters_client, headers=owner_headers, game_name="test-alpha")

    response = characters_client.get(f"/api/characters/{created['id']}", headers=other_headers)
    assert response.status_code == 404


def test_get_character_by_id_returns_404_for_missing_character(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-missing@example.com")

    response = characters_client.get("/api/characters/11111111-1111-1111-1111-111111111111", headers=headers)
    assert response.status_code == 404


def test_delete_character_deletes_owned_character(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-delete@example.com")
    created = _create_character(characters_client, headers=headers, game_name="test-alpha")

    delete_response = characters_client.delete(f"/api/characters/{created['id']}", headers=headers)
    assert delete_response.status_code == 204

    get_response = characters_client.get(f"/api/characters/{created['id']}", headers=headers)
    assert get_response.status_code == 404


def test_delete_character_returns_404_for_other_users_character(characters_client: TestClient) -> None:
    owner_headers = _auth_headers(characters_client, "char-delete-owner@example.com")
    other_headers = _auth_headers(characters_client, "char-delete-other@example.com")

    created = _create_character(characters_client, headers=owner_headers, game_name="test-alpha")

    response = characters_client.delete(f"/api/characters/{created['id']}", headers=other_headers)
    assert response.status_code == 404

    still_exists = characters_client.get(f"/api/characters/{created['id']}", headers=owner_headers)
    assert still_exists.status_code == 200


def test_patch_character_renames_owned_character(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-rename@example.com")
    created = _create_character(characters_client, headers=headers, game_name="test-alpha")

    response = characters_client.patch(
        f"/api/characters/{created['id']}",
        json={"name": "Renamed Character"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Character"


def test_patch_character_rejects_whitespace_name(characters_client: TestClient) -> None:
    headers = _auth_headers(characters_client, "char-blank-rename@example.com")
    created = _create_character(characters_client, headers=headers, game_name="test-alpha")

    response = characters_client.patch(
        f"/api/characters/{created['id']}",
        json={"name": "   "},
        headers=headers,
    )
    assert response.status_code == 422


def test_patch_character_returns_404_for_other_users_character(characters_client: TestClient) -> None:
    owner_headers = _auth_headers(characters_client, "char-patch-owner@example.com")
    other_headers = _auth_headers(characters_client, "char-patch-other@example.com")

    created = _create_character(characters_client, headers=owner_headers, game_name="test-alpha")

    response = characters_client.patch(
        f"/api/characters/{created['id']}",
        json={"name": "Hijacked"},
        headers=other_headers,
    )
    assert response.status_code == 404

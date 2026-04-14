"""Tests for the /games router and game dependency helpers."""

from types import SimpleNamespace
from typing import Any, Dict

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from oscilla.dependencies.games import get_registry
from oscilla.engine.models.character_config import CharacterConfigManifest
from oscilla.engine.models.game import GameManifest
from oscilla.engine.models.skill import SkillManifest
from oscilla.engine.models.time import GameTimeSpec
from oscilla.engine.registry import ContentRegistry
from oscilla.www import app


@pytest.fixture
def games_client() -> TestClient:
    """TestClient with app.state.registries overridden for games router tests."""
    client = TestClient(app)
    app.state.registries = {
        "test-alpha": _build_registry(name="test-alpha", display_name="Test Alpha", with_skills=False, with_time=False),
        "test-beta": _build_registry(name="test-beta", display_name="Test Beta", with_skills=True, with_time=True),
    }
    return client


def _build_registry(name: str, display_name: str, with_skills: bool, with_time: bool) -> ContentRegistry:
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
                    {"name": "power", "type": "int", "derived": "{{ stats.health }}"},
                ],
            },
        }
    )

    if with_skills:
        skill = SkillManifest.model_validate(
            {
                "apiVersion": "oscilla/v1",
                "kind": "Skill",
                "metadata": {"name": "test-skill"},
                "spec": {
                    "displayName": "Test Skill",
                    "contexts": ["combat"],
                },
            }
        )
        registry.skills.register(manifest=skill)

    return registry


def test_get_games_returns_all_loaded_games(games_client: TestClient) -> None:
    response = games_client.get("/api/games")
    assert response.status_code == 200

    body = response.json()
    assert len(body) == 2
    names = {row["name"] for row in body}
    assert names == {"test-alpha", "test-beta"}


def test_get_games_returns_empty_when_no_games_loaded(games_client: TestClient) -> None:
    app.state.registries = {}
    response = games_client.get("/api/games")
    assert response.status_code == 200
    assert response.json() == []


def test_get_game_returns_single_game(games_client: TestClient) -> None:
    response = games_client.get("/api/games/test-alpha")
    assert response.status_code == 200

    body = response.json()
    assert body["name"] == "test-alpha"
    assert body["display_name"] == "Test Alpha"


def test_get_game_returns_404_for_unknown_game(games_client: TestClient) -> None:
    response = games_client.get("/api/games/does-not-exist")
    assert response.status_code == 404


def test_feature_flags_reflect_registry_state(games_client: TestClient) -> None:
    response = games_client.get("/api/games")
    assert response.status_code == 200

    by_name = {row["name"]: row for row in response.json()}
    alpha_flags = by_name["test-alpha"]["features"]
    beta_flags = by_name["test-beta"]["features"]

    assert alpha_flags["has_skills"] is False
    assert beta_flags["has_skills"] is True


def test_ingame_time_flag_uses_time_spec_presence(games_client: TestClient) -> None:
    response = games_client.get("/api/games")
    assert response.status_code == 200

    by_name = {row["name"]: row for row in response.json()}
    assert by_name["test-alpha"]["features"]["has_ingame_time"] is False
    assert by_name["test-beta"]["features"]["has_ingame_time"] is True


def test_get_registry_dependency() -> None:
    known_registry = _build_registry(name="known", display_name="Known", with_skills=False, with_time=False)
    app_stub = FastAPI()
    app_stub.state.registries = {"known": known_registry}
    request_stub = SimpleNamespace(app=app_stub)

    resolved = get_registry(game_name="known", request=request_stub)
    assert resolved is known_registry

    with pytest.raises(HTTPException) as exc:
        get_registry(game_name="unknown", request=request_stub)
    assert exc.value.status_code == 404

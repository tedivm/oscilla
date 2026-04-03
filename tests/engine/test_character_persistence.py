"""Unit tests for CharacterState serialization: to_dict / from_dict round-trips."""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from oscilla.engine.character import AdventurePosition, CharacterState
from oscilla.engine.registry import ContentRegistry


def test_to_dict_round_trips_all_fields(base_player: CharacterState) -> None:
    """to_dict → from_dict with matching config produces identical state."""
    base_player.level = 3
    base_player.xp = 150
    base_player.hp = 15
    base_player.add_item(ref="test-sword", quantity=2)
    base_player.grant_milestone("first-victory")
    base_player.statistics.record_enemy_defeated("test-enemy")
    base_player.statistics.record_location_visited("test-dungeon")
    base_player.statistics.record_adventure_completed("test-narrative")
    base_player.active_quests["test-quest"] = "stage-1"
    base_player.completed_quests.add("old-quest")
    base_player.active_adventure = AdventurePosition(
        adventure_ref="test-narrative",
        step_index=2,
        step_state={"enemy_hp": 5},
    )

    data = base_player.to_dict()
    from oscilla.engine.loader import load
    from tests.engine.conftest import FIXTURES

    minimal, _warnings = load(FIXTURES / "minimal")
    assert minimal.character_config is not None

    restored = CharacterState.from_dict(
        data=data,
        character_config=minimal.character_config,
    )

    assert restored.character_id == base_player.character_id
    assert restored.name == base_player.name
    assert restored.level == base_player.level
    assert restored.xp == base_player.xp
    assert restored.hp == base_player.hp
    assert restored.max_hp == base_player.max_hp
    assert restored.stacks == base_player.stacks
    assert restored.milestones == base_player.milestones
    assert restored.active_quests == base_player.active_quests
    assert restored.completed_quests == base_player.completed_quests
    assert restored.statistics.enemies_defeated == base_player.statistics.enemies_defeated
    assert restored.statistics.locations_visited == base_player.statistics.locations_visited
    assert restored.statistics.adventures_completed == base_player.statistics.adventures_completed
    assert restored.active_adventure is not None
    assert restored.active_adventure.adventure_ref == "test-narrative"
    assert restored.active_adventure.step_index == 2
    assert restored.active_adventure.step_state == {"enemy_hp": 5}


def test_from_dict_matching_config(minimal_registry: ContentRegistry) -> None:
    """from_dict with an exactly-matching config produces the same stats."""
    assert minimal_registry.character_config is not None
    data = {
        "character_id": str(uuid4()),
        "iteration": 0,
        "name": "TestHero",
        "character_class": None,
        "level": 1,
        "xp": 0,
        "hp": 20,
        "max_hp": 20,
        "current_location": None,
        "milestones": [],
        "inventory": {},
        "equipment": {},
        "active_quests": {},
        "completed_quests": [],
        "stats": {"strength": 10},
        "statistics": {"enemies_defeated": {}, "locations_visited": {}, "adventures_completed": {}},
        "active_adventure": None,
    }
    state = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert state.stats["strength"] == 10
    assert state.name == "TestHero"
    assert state.level == 1


def test_from_dict_injects_missing_stat_default(minimal_registry: ContentRegistry) -> None:
    """A stat in the config but absent from saved data is injected with its default value."""
    assert minimal_registry.character_config is not None
    data = {
        "character_id": str(uuid4()),
        "iteration": 0,
        "name": "MissingStats",
        "character_class": None,
        "level": 1,
        "xp": 0,
        "hp": 20,
        "max_hp": 20,
        "current_location": None,
        "milestones": [],
        "inventory": {},
        "equipment": {},
        "active_quests": {},
        "completed_quests": [],
        "stats": {},  # 'strength' is intentionally absent
        "statistics": {"enemies_defeated": {}, "locations_visited": {}, "adventures_completed": {}},
        "active_adventure": None,
    }
    state = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    # 'strength' default is 10 in the minimal fixture
    assert state.stats["strength"] == 10


def test_from_dict_drops_unknown_stat_and_logs_warning(
    minimal_registry: ContentRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A stat in save data but absent from config is dropped, and a WARNING is logged."""
    assert minimal_registry.character_config is not None
    data = {
        "character_id": str(uuid4()),
        "iteration": 0,
        "name": "StaleStats",
        "character_class": None,
        "level": 1,
        "xp": 0,
        "hp": 20,
        "max_hp": 20,
        "current_location": None,
        "milestones": [],
        "inventory": {},
        "equipment": {},
        "active_quests": {},
        "completed_quests": [],
        "stats": {"strength": 10, "obsolete_stat": 999},
        "statistics": {"enemies_defeated": {}, "locations_visited": {}, "adventures_completed": {}},
        "active_adventure": None,
    }
    with caplog.at_level(logging.WARNING, logger="oscilla.engine.character"):
        state = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)

    assert "obsolete_stat" not in state.stats
    assert any("obsolete_stat" in record.message for record in caplog.records)


def test_from_dict_clears_stale_adventure_ref_and_logs_warning(
    minimal_registry: ContentRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If active_adventure.adventure_ref is unknown in the registry, it is cleared with WARNING."""
    assert minimal_registry.character_config is not None
    data = {
        "character_id": str(uuid4()),
        "iteration": 0,
        "name": "StuckHero",
        "character_class": None,
        "level": 1,
        "xp": 0,
        "hp": 20,
        "max_hp": 20,
        "current_location": None,
        "milestones": [],
        "inventory": {},
        "equipment": {},
        "active_quests": {},
        "completed_quests": [],
        "stats": {"strength": 10},
        "statistics": {"enemies_defeated": {}, "locations_visited": {}, "adventures_completed": {}},
        "active_adventure": {
            "adventure_ref": "nonexistent-adventure-xyz",
            "step_index": 3,
            "step_state": {"enemy_hp": 7},
        },
    }
    with caplog.at_level(logging.WARNING, logger="oscilla.engine.character"):
        state = CharacterState.from_dict(
            data=data,
            character_config=minimal_registry.character_config,
            registry=minimal_registry,
        )

    assert state.active_adventure is None
    assert any("nonexistent-adventure-xyz" in record.message for record in caplog.records)

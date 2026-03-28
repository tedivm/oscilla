"""Tests for PlayerState — factory, XP/level-up, inventory, milestones, equipment."""

from __future__ import annotations

import pytest

from oscilla.engine.player import PlayerState
from oscilla.engine.registry import ContentRegistry


def test_new_player_defaults(base_player: PlayerState) -> None:
    assert base_player.level == 1
    assert base_player.xp == 0
    assert base_player.hp == 20
    assert base_player.max_hp == 20
    assert base_player.inventory == {}
    assert base_player.milestones == set()
    assert base_player.active_adventure is None


def test_new_player_stats_from_char_config(base_player: PlayerState) -> None:
    # The minimal fixture defines strength with default 10
    assert base_player.stats["strength"] == 10


def test_add_xp_no_level_up(minimal_registry: ContentRegistry) -> None:
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    # Use thresholds [1000, 2000, 3000] (none reachable from 0) to test no-level-up path
    player = PlayerState.new_player(
        name="NoLevel",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    levels = player.add_xp(
        amount=50,
        xp_thresholds=[1000, 2000, 3000],
        hp_per_level=5,
    )
    assert levels == []
    assert player.level == 1
    assert player.xp == 50


def test_add_xp_triggers_level_up(minimal_registry: ContentRegistry) -> None:
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    player = PlayerState.new_player(
        name="LevelUp",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    hp_per_level = minimal_registry.game.spec.hp_formula.hp_per_level

    # Use explicit thresholds: 50 XP → level 2, 200 XP → level 3
    levels = player.add_xp(amount=50, xp_thresholds=[50, 200, 500], hp_per_level=hp_per_level)
    assert 2 in levels
    assert player.level == 2
    assert player.max_hp == 20 + hp_per_level  # base_hp=20, hp_per_level=5


def test_grant_and_has_milestone(base_player: PlayerState) -> None:
    assert not base_player.has_milestone("test-flag")
    base_player.grant_milestone("test-flag")
    assert base_player.has_milestone("test-flag")


def test_grant_milestone_idempotent(base_player: PlayerState) -> None:
    base_player.grant_milestone("idempotent-flag")
    base_player.grant_milestone("idempotent-flag")
    # Set deduplicates — should still only appear once
    assert base_player.has_milestone("idempotent-flag")
    assert len([m for m in base_player.milestones if m == "idempotent-flag"]) == 1


def test_add_and_remove_item(base_player: PlayerState) -> None:
    base_player.add_item(ref="potion", quantity=3)
    assert base_player.inventory["potion"] == 3
    base_player.remove_item(ref="potion", quantity=2)
    assert base_player.inventory["potion"] == 1
    base_player.remove_item(ref="potion", quantity=1)
    assert "potion" not in base_player.inventory


def test_remove_item_raises_on_insufficient(base_player: PlayerState) -> None:
    with pytest.raises(ValueError, match="Cannot remove"):
        base_player.remove_item(ref="missing-item", quantity=1)


def test_equip_item(base_player: PlayerState) -> None:
    base_player.add_item(ref="iron-sword", quantity=1)
    base_player.equip(item_ref="iron-sword", slot="weapon")
    assert base_player.equipment["weapon"] == "iron-sword"
    assert "iron-sword" not in base_player.inventory


def test_equip_displaces_existing(base_player: PlayerState) -> None:
    base_player.add_item(ref="iron-sword", quantity=1)
    base_player.add_item(ref="golden-sword", quantity=1)
    base_player.equip(item_ref="iron-sword", slot="weapon")
    base_player.equip(item_ref="golden-sword", slot="weapon")
    assert base_player.equipment["weapon"] == "golden-sword"
    # displaced item returned to inventory
    assert base_player.inventory.get("iron-sword", 0) == 1


def test_equip_raises_if_not_in_inventory(base_player: PlayerState) -> None:
    with pytest.raises(ValueError, match="Cannot equip"):
        base_player.equip(item_ref="imaginary-sword", slot="weapon")


def test_record_tracking_methods(base_player: PlayerState) -> None:
    """Test enemy defeated, location visited, and adventure completed tracking."""
    # Test enemy defeated tracking
    base_player.statistics.record_enemy_defeated("goblin")
    base_player.statistics.record_enemy_defeated("goblin")
    base_player.statistics.record_enemy_defeated("orc")
    assert base_player.statistics.enemies_defeated["goblin"] == 2
    assert base_player.statistics.enemies_defeated["orc"] == 1

    # Test location visited tracking
    base_player.statistics.record_location_visited("forest")
    base_player.statistics.record_location_visited("forest")
    base_player.statistics.record_location_visited("cave")
    assert base_player.statistics.locations_visited["forest"] == 2
    assert base_player.statistics.locations_visited["cave"] == 1

    # Test adventure completed tracking
    base_player.statistics.record_adventure_completed("quest-1")
    base_player.statistics.record_adventure_completed("quest-1")
    base_player.statistics.record_adventure_completed("quest-2")
    assert base_player.statistics.adventures_completed["quest-1"] == 2
    assert base_player.statistics.adventures_completed["quest-2"] == 1

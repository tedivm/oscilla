"""Tests for CharacterState — factory, XP/level-up, inventory, milestones, equipment."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from oscilla.engine.character import _INT64_MAX, _INT64_MIN, CharacterState, ItemInstance
from oscilla.engine.registry import ContentRegistry


def test_new_player_defaults(base_player: CharacterState) -> None:
    assert base_player.level == 1
    assert base_player.xp == 0
    assert base_player.hp == 20
    assert base_player.max_hp == 20
    assert base_player.stacks == {}
    assert base_player.instances == []
    assert base_player.milestones == set()
    assert base_player.active_adventure is None


def test_new_player_stats_from_char_config(base_player: CharacterState) -> None:
    # The minimal fixture defines strength with default 10
    assert base_player.stats["strength"] == 10


def test_add_xp_no_level_up(minimal_registry: ContentRegistry) -> None:
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    # Use thresholds [1000, 2000, 3000] (none reachable from 0) to test no-level-up path
    player = CharacterState.new_character(
        name="NoLevel",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    levels_gained, levels_lost = player.add_xp(
        amount=50,
        xp_thresholds=[1000, 2000, 3000],
        hp_per_level=5,
    )
    assert levels_gained == []
    assert levels_lost == []
    assert player.level == 1
    assert player.xp == 50


def test_add_xp_triggers_level_up(minimal_registry: ContentRegistry) -> None:
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="LevelUp",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    hp_per_level = minimal_registry.game.spec.hp_formula.hp_per_level

    # Use explicit thresholds: 50 XP → level 2, 200 XP → level 3
    levels_gained, levels_lost = player.add_xp(amount=50, xp_thresholds=[50, 200, 500], hp_per_level=hp_per_level)
    assert 2 in levels_gained
    assert levels_lost == []
    assert player.level == 2
    assert player.max_hp == 20 + hp_per_level  # base_hp=20, hp_per_level=5


def test_grant_and_has_milestone(base_player: CharacterState) -> None:
    assert not base_player.has_milestone("test-flag")
    base_player.grant_milestone("test-flag")
    assert base_player.has_milestone("test-flag")


def test_grant_milestone_idempotent(base_player: CharacterState) -> None:
    base_player.grant_milestone("idempotent-flag")
    base_player.grant_milestone("idempotent-flag")
    # Set deduplicates — should still only appear once
    assert base_player.has_milestone("idempotent-flag")
    assert len([m for m in base_player.milestones if m == "idempotent-flag"]) == 1


def test_add_and_remove_item(base_player: CharacterState) -> None:
    base_player.add_item(ref="potion", quantity=3)
    assert base_player.stacks["potion"] == 3
    base_player.remove_item(ref="potion", quantity=2)
    assert base_player.stacks["potion"] == 1
    base_player.remove_item(ref="potion", quantity=1)
    assert "potion" not in base_player.stacks


def test_remove_item_raises_on_insufficient(base_player: CharacterState) -> None:
    with pytest.raises(ValueError, match="Cannot remove"):
        base_player.remove_item(ref="missing-item", quantity=1)


def test_equip_item(base_player: CharacterState) -> None:
    inst = ItemInstance(instance_id=UUID("00000000-0000-0000-0000-000000000001"), item_ref="iron-sword")
    base_player.instances.append(inst)
    base_player.equip_instance(instance_id=inst.instance_id, slots=["weapon"])
    assert base_player.equipment["weapon"] == inst.instance_id
    # Instance stays in instances list — equipment dict records the slot mapping
    assert inst in base_player.instances


def test_equip_displaces_existing(base_player: CharacterState) -> None:
    inst1 = ItemInstance(instance_id=UUID("00000000-0000-0000-0000-000000000001"), item_ref="iron-sword")
    inst2 = ItemInstance(instance_id=UUID("00000000-0000-0000-0000-000000000002"), item_ref="golden-sword")
    base_player.instances.extend([inst1, inst2])
    base_player.equip_instance(instance_id=inst1.instance_id, slots=["weapon"])
    base_player.equip_instance(instance_id=inst2.instance_id, slots=["weapon"])
    assert base_player.equipment["weapon"] == inst2.instance_id
    # displaced item returned to instances
    assert inst1 in base_player.instances


def test_equip_raises_if_not_in_instances(base_player: CharacterState) -> None:
    with pytest.raises(ValueError, match="not found"):
        base_player.equip_instance(instance_id=UUID("00000000-0000-0000-0000-000000000099"), slots=["weapon"])


def test_record_tracking_methods(base_player: CharacterState) -> None:
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


def test_add_xp_negative_single_level_down(minimal_registry: ContentRegistry) -> None:
    """Test level-down with negative XP losing a single level."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="LevelDown",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    hp_per_level = minimal_registry.game.spec.hp_formula.hp_per_level

    # Level up to level 3 first: 50 XP → level 2, 200 XP → level 3
    player.add_xp(amount=250, xp_thresholds=[50, 200, 500], hp_per_level=hp_per_level)
    assert player.level == 3
    assert player.xp == 250

    # Now lose XP to go back to level 2: need to go below 200 XP threshold
    levels_gained, levels_lost = player.add_xp(amount=-80, xp_thresholds=[50, 200, 500], hp_per_level=hp_per_level)
    assert levels_gained == []
    assert levels_lost == [3]  # lost level 3, now level 2
    assert player.level == 2
    assert player.xp == 170


def test_add_xp_negative_multi_level_down(minimal_registry: ContentRegistry) -> None:
    """Test level-down with negative XP losing multiple levels."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="MultiDown",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    hp_per_level = minimal_registry.game.spec.hp_formula.hp_per_level

    # Level up to level 4: 50 → level 2, 200 → level 3, 500 → level 4
    player.add_xp(amount=600, xp_thresholds=[50, 200, 500], hp_per_level=hp_per_level)
    assert player.level == 4
    assert player.xp == 600

    # Lose enough XP to drop to level 1: go below 50 XP threshold
    levels_gained, levels_lost = player.add_xp(amount=-580, xp_thresholds=[50, 200, 500], hp_per_level=hp_per_level)
    assert levels_gained == []
    assert levels_lost == [4, 3, 2]  # lost levels 4→3→2→1
    assert player.level == 1
    assert player.xp == 20


def test_add_xp_negative_xp_floor_zero(minimal_registry: ContentRegistry) -> None:
    """Test that XP cannot go below 0 (floor at 0)."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="XPFloor",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )

    # Start with 50 XP
    player.add_xp(amount=50, xp_thresholds=[100, 200, 500], hp_per_level=5)
    assert player.xp == 50

    # Try to lose more XP than available
    levels_gained, levels_lost = player.add_xp(amount=-80, xp_thresholds=[100, 200, 500], hp_per_level=5)
    assert levels_gained == []
    assert levels_lost == []  # no level change since we're already at level 1
    assert player.level == 1
    assert player.xp == 0  # XP floors at 0


def test_add_xp_negative_level_floor_one(minimal_registry: ContentRegistry) -> None:
    """Test that level cannot go below 1 (floor at level 1)."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="LevelFloor",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )

    # Start at level 1 with 0 XP, try to lose more XP
    levels_gained, levels_lost = player.add_xp(amount=-100, xp_thresholds=[50, 200, 500], hp_per_level=5)
    assert levels_gained == []
    assert levels_lost == []
    assert player.level == 1  # level floors at 1
    assert player.xp == 0  # XP floors at 0


def test_add_xp_negative_hp_cap_adjustment(minimal_registry: ContentRegistry) -> None:
    """Test that HP is capped to new max_hp when leveling down."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="HPCap",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    hp_per_level = 5  # explicit for clarity

    # Level up to level 3, max_hp will be 20(base) + 2*5 = 30
    player.add_xp(amount=250, xp_thresholds=[50, 200, 500], hp_per_level=hp_per_level)
    assert player.level == 3
    assert player.max_hp == 30

    # Set current HP to max
    player.hp = player.max_hp
    assert player.hp == 30

    # Level down to level 2: new max_hp will be 20 + 1*5 = 25
    levels_gained, levels_lost = player.add_xp(amount=-80, xp_thresholds=[50, 200, 500], hp_per_level=hp_per_level)
    assert levels_lost == [3]
    assert player.level == 2
    assert player.max_hp == 25
    assert player.hp == 25  # HP was capped to new max_hp


def test_add_xp_return_tuple_structure(minimal_registry: ContentRegistry) -> None:
    """Test that add_xp returns proper tuple structure (levels_gained, levels_lost)."""
    assert minimal_registry.game is not None
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="TupleTest",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )

    # Test gaining levels
    result = player.add_xp(amount=250, xp_thresholds=[50, 200, 500], hp_per_level=5)
    assert isinstance(result, tuple)
    assert len(result) == 2
    levels_gained, levels_lost = result
    assert isinstance(levels_gained, list)
    assert isinstance(levels_lost, list)
    assert levels_gained == [2, 3]  # gained levels 2 and 3
    assert levels_lost == []

    # Test losing levels
    result = player.add_xp(amount=-220, xp_thresholds=[50, 200, 500], hp_per_level=5)
    levels_gained, levels_lost = result
    assert levels_gained == []
    assert levels_lost == [3, 2]  # lost levels 3→2→1


# ---------------------------------------------------------------------------
# CharacterState.set_stat() — INT64 clamp backstop tests
# ---------------------------------------------------------------------------


def _make_bare_player() -> CharacterState:
    return CharacterState(
        character_id=uuid4(),
        name="T",
        character_class=None,
        level=1,
        xp=0,
        hp=20,
        max_hp=20,
        iteration=0,
        current_location=None,
        stats={"gold": 100},
    )


def test_set_stat_within_range_is_unchanged() -> None:
    player = _make_bare_player()
    player.set_stat(name="gold", value=500)
    assert player.stats["gold"] == 500


def test_set_stat_clamps_above_int64_max(caplog: pytest.LogCaptureFixture) -> None:
    player = _make_bare_player()
    over = _INT64_MAX + 1
    with caplog.at_level("WARNING"):
        player.set_stat(name="gold", value=over)
    assert player.stats["gold"] == _INT64_MAX
    assert "clamped" in caplog.text


def test_set_stat_clamps_below_int64_min(caplog: pytest.LogCaptureFixture) -> None:
    player = _make_bare_player()
    under = _INT64_MIN - 1
    with caplog.at_level("WARNING"):
        player.set_stat(name="gold", value=under)
    assert player.stats["gold"] == _INT64_MIN
    assert "clamped" in caplog.text


def test_set_stat_at_int64_boundary_is_not_clamped() -> None:
    player = _make_bare_player()
    player.set_stat(name="gold", value=_INT64_MAX)
    assert player.stats["gold"] == _INT64_MAX
    player.set_stat(name="gold", value=_INT64_MIN)
    assert player.stats["gold"] == _INT64_MIN


# ---------------------------------------------------------------------------
# CharacterState serialization — tick fields (task 10.5)
# ---------------------------------------------------------------------------


def test_ticks_round_trip(minimal_registry: ContentRegistry) -> None:
    """internal_ticks and game_ticks survive a to_dict()/from_dict() round-trip."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="TickTester",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    player.internal_ticks = 42
    player.game_ticks = 17
    player.era_started_at_ticks = {"ancient": 5}
    player.era_ended_at_ticks = {"ancient": 10}
    player.adventure_last_completed_at_ticks = {"quest-x": 3}

    data = player.to_dict()
    assert data["internal_ticks"] == 42
    assert data["game_ticks"] == 17

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert restored.internal_ticks == 42
    assert restored.game_ticks == 17
    assert restored.era_started_at_ticks == {"ancient": 5}
    assert restored.era_ended_at_ticks == {"ancient": 10}
    assert restored.adventure_last_completed_at_ticks == {"quest-x": 3}


def test_ticks_default_to_zero_when_absent(minimal_registry: ContentRegistry) -> None:
    """Deserializing an old save without tick keys produces zeros (backward compat)."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="OldSave",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    data = player.to_dict()
    # Simulate an old save by removing the new keys.
    data.pop("internal_ticks", None)
    data.pop("game_ticks", None)
    data.pop("era_started_at_ticks", None)
    data.pop("era_ended_at_ticks", None)
    data.pop("adventure_last_completed_at_ticks", None)

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert restored.internal_ticks == 0
    assert restored.game_ticks == 0
    assert restored.era_started_at_ticks == {}
    assert restored.era_ended_at_ticks == {}
    assert restored.adventure_last_completed_at_ticks == {}


def test_old_adventure_tick_key_mapped_to_new_key(minimal_registry: ContentRegistry) -> None:
    """adventure_last_completed_at_total (deprecated key) maps to adventure_last_completed_at_ticks."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="Migration",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    data = player.to_dict()
    # Simulate an old save using the deprecated key name.
    data.pop("adventure_last_completed_at_ticks", None)
    data["adventure_last_completed_at_total"] = {"old-quest": 7}

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    assert restored.adventure_last_completed_at_ticks == {"old-quest": 7}


def test_new_adventure_tick_key_takes_precedence(minimal_registry: ContentRegistry) -> None:
    """New key adventure_last_completed_at_ticks wins over the deprecated key when both present."""
    assert minimal_registry.character_config is not None
    player = CharacterState.new_character(
        name="Precedence",
        game_manifest=minimal_registry.game,
        character_config=minimal_registry.character_config,
    )
    data = player.to_dict()
    data["adventure_last_completed_at_ticks"] = {"new-quest": 99}
    data["adventure_last_completed_at_total"] = {"old-quest": 1}

    restored = CharacterState.from_dict(data=data, character_config=minimal_registry.character_config)
    # new key takes precedence; old key is ignored
    assert restored.adventure_last_completed_at_ticks == {"new-quest": 99}
    assert "old-quest" not in restored.adventure_last_completed_at_ticks

"""Integration tests for on_stat_threshold fire_mode: each vs fire_mode: highest.

Covers task 11.3:
- fire_mode: each fires all upward crossings in ascending order
- fire_mode: highest fires only the single highest crossed threshold
- Mixed modes in the same registry operate independently
- Default fire_mode is "each" (backward-compatible)
- A single threshold crossing behaves the same regardless of fire_mode
- Downward crossings do not fire
"""

from __future__ import annotations

from oscilla.engine.models.game import StatThresholdTrigger
from oscilla.engine.steps.effects import _fire_threshold_triggers
from tests.fixtures.content.trigger_tests import build_trigger_test_registry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registry_with_thresholds(*thresholds: StatThresholdTrigger):  # type: ignore[no-untyped-def]
    """Build a trigger registry with the given threshold entries pre-wired."""
    # Each unique trigger name must also appear in trigger_adventures to be
    # enqueued. We map every name to itself using test-stat-boost-adventure.
    names = {t.name for t in thresholds}
    registry = build_trigger_test_registry(
        on_stat_threshold=list(thresholds),
        trigger_adventures={name: ["test-stat-boost-adventure"] for name in names},
    )
    return registry


# ---------------------------------------------------------------------------
# fire_mode: each
# ---------------------------------------------------------------------------


async def test_each_fires_all_crossings_in_ascending_order() -> None:
    """fire_mode:each enqueues all crossed thresholds in ascending threshold order."""
    registry = _registry_with_thresholds(
        StatThresholdTrigger(stat="xp", threshold=10, name="xp-10", fire_mode="each"),
        StatThresholdTrigger(stat="xp", threshold=20, name="xp-20", fire_mode="each"),
        StatThresholdTrigger(stat="xp", threshold=30, name="xp-30", fire_mode="each"),
    )
    player = registry.character_config  # type: ignore[assignment]
    # Build a fresh player using the trigger_tests fixture.
    assert registry.game is not None
    assert registry.character_config is not None
    from oscilla.engine.character import CharacterState

    player = CharacterState.new_character(
        name="EachHero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )

    # Jump from 0 → 35, crossing thresholds 10, 20, and 30.
    await _fire_threshold_triggers(
        stat_name="xp",
        old_value=0,
        new_value=35,
        player=player,
        registry=registry,
    )

    assert player.pending_triggers == ["xp-10", "xp-20", "xp-30"]


async def test_each_fires_only_crossed_thresholds() -> None:
    """fire_mode:each does not fire thresholds not crossed in the current jump."""
    registry = _registry_with_thresholds(
        StatThresholdTrigger(stat="xp", threshold=10, name="xp-10", fire_mode="each"),
        StatThresholdTrigger(stat="xp", threshold=50, name="xp-50", fire_mode="each"),
    )
    assert registry.game is not None
    assert registry.character_config is not None
    from oscilla.engine.character import CharacterState

    player = CharacterState.new_character(
        name="PartialEachHero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )

    # Jump from 0 → 25: crosses 10 but not 50.
    await _fire_threshold_triggers(
        stat_name="xp",
        old_value=0,
        new_value=25,
        player=player,
        registry=registry,
    )

    assert player.pending_triggers == ["xp-10"]


# ---------------------------------------------------------------------------
# fire_mode: highest
# ---------------------------------------------------------------------------


async def test_highest_fires_only_top_crossed_threshold() -> None:
    """fire_mode:highest enqueues only the single highest crossed threshold."""
    registry = _registry_with_thresholds(
        StatThresholdTrigger(stat="xp", threshold=10, name="xp-10", fire_mode="highest"),
        StatThresholdTrigger(stat="xp", threshold=20, name="xp-20", fire_mode="highest"),
        StatThresholdTrigger(stat="xp", threshold=30, name="xp-30", fire_mode="highest"),
    )
    assert registry.game is not None
    assert registry.character_config is not None
    from oscilla.engine.character import CharacterState

    player = CharacterState.new_character(
        name="HighestHero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )

    # Jump from 0 → 35, crossing thresholds 10, 20, and 30.
    await _fire_threshold_triggers(
        stat_name="xp",
        old_value=0,
        new_value=35,
        player=player,
        registry=registry,
    )

    # Only the highest crossed threshold fires.
    assert player.pending_triggers == ["xp-30"]


async def test_highest_fires_single_when_one_threshold_crossed() -> None:
    """fire_mode:highest fires the single threshold when only one is crossed."""
    registry = _registry_with_thresholds(
        StatThresholdTrigger(stat="xp", threshold=10, name="xp-10", fire_mode="highest"),
        StatThresholdTrigger(stat="xp", threshold=50, name="xp-50", fire_mode="highest"),
    )
    assert registry.game is not None
    assert registry.character_config is not None
    from oscilla.engine.character import CharacterState

    player = CharacterState.new_character(
        name="SingleHighHero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )

    # Jump from 0 → 15: crosses 10 but not 50.
    await _fire_threshold_triggers(
        stat_name="xp",
        old_value=0,
        new_value=15,
        player=player,
        registry=registry,
    )

    assert player.pending_triggers == ["xp-10"]


# ---------------------------------------------------------------------------
# Mixed modes
# ---------------------------------------------------------------------------


async def test_mixed_modes_operate_independently() -> None:
    """fire_mode:each and fire_mode:highest entries fire independently in one crossing."""
    registry = _registry_with_thresholds(
        StatThresholdTrigger(stat="xp", threshold=10, name="xp-each-10", fire_mode="each"),
        StatThresholdTrigger(stat="xp", threshold=20, name="xp-each-20", fire_mode="each"),
        StatThresholdTrigger(stat="xp", threshold=10, name="xp-max-10", fire_mode="highest"),
        StatThresholdTrigger(stat="xp", threshold=20, name="xp-max-20", fire_mode="highest"),
    )
    assert registry.game is not None
    assert registry.character_config is not None
    from oscilla.engine.character import CharacterState

    player = CharacterState.new_character(
        name="MixedHero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )

    # Jump from 0 → 25: crosses both 10 and 20.
    await _fire_threshold_triggers(
        stat_name="xp",
        old_value=0,
        new_value=25,
        player=player,
        registry=registry,
    )

    # "each" group enqueues both in ascending order first,
    # then "highest" group enqueues only xp-max-20.
    assert player.pending_triggers == ["xp-each-10", "xp-each-20", "xp-max-20"]


# ---------------------------------------------------------------------------
# Default fire_mode is "each"
# ---------------------------------------------------------------------------


async def test_default_fire_mode_is_each() -> None:
    """StatThresholdTrigger without an explicit fire_mode defaults to 'each'."""
    trigger = StatThresholdTrigger(stat="xp", threshold=10, name="xp-default")
    assert trigger.fire_mode == "each"

    registry = _registry_with_thresholds(
        StatThresholdTrigger(stat="xp", threshold=10, name="xp-default"),
        StatThresholdTrigger(stat="xp", threshold=20, name="xp-default-20"),
    )
    assert registry.game is not None
    assert registry.character_config is not None
    from oscilla.engine.character import CharacterState

    player = CharacterState.new_character(
        name="DefaultHero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )

    await _fire_threshold_triggers(
        stat_name="xp",
        old_value=0,
        new_value=25,
        player=player,
        registry=registry,
    )

    # Both fire because default is "each".
    assert player.pending_triggers == ["xp-default", "xp-default-20"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_downward_crossing_does_not_fire() -> None:
    """Thresholds do not fire when the stat value decreases."""
    registry = _registry_with_thresholds(
        StatThresholdTrigger(stat="xp", threshold=10, name="xp-10", fire_mode="each"),
    )
    assert registry.game is not None
    assert registry.character_config is not None
    from oscilla.engine.character import CharacterState

    player = CharacterState.new_character(
        name="DownHero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )

    # Move downward: 50 → 5 (crosses 10 downward — should not fire).
    await _fire_threshold_triggers(
        stat_name="xp",
        old_value=50,
        new_value=5,
        player=player,
        registry=registry,
    )

    assert player.pending_triggers == []


async def test_no_fire_when_already_above_threshold() -> None:
    """No threshold fire when the old value already exceeds the threshold."""
    registry = _registry_with_thresholds(
        StatThresholdTrigger(stat="xp", threshold=10, name="xp-10", fire_mode="each"),
    )
    assert registry.game is not None
    assert registry.character_config is not None
    from oscilla.engine.character import CharacterState

    player = CharacterState.new_character(
        name="AlreadyHero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )

    # Move from 20 → 30: threshold 10 was already crossed before, should not re-fire.
    await _fire_threshold_triggers(
        stat_name="xp",
        old_value=20,
        new_value=30,
        player=player,
        registry=registry,
    )

    assert player.pending_triggers == []

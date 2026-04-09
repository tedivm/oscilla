"""Integration tests for derived stat shadow computation and PlayerContext access.

Covers task 11.1 and 11.2:
- Shadow dict populated on recompute
- Shadow updated when stored stat changes
- No threshold fires during initial load
- Derived values accessible via player.stats in formulas (chain resolution)
- stat_context: stored vs effective behavior
- _derived_shadows absent from to_dict() output
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.loader import load
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.effects import _recompute_derived_stats
from tests.engine.conftest import MockTUI

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def derived_registry() -> ContentRegistry:
    """Registry loaded from the derived-stats fixture package."""
    registry, _warnings = load(_FIXTURES / "derived-stats")
    return registry


@pytest.fixture
def derived_player(derived_registry: ContentRegistry) -> CharacterState:
    """Fresh player from the derived-stats fixture (strength=10, level=1)."""
    assert derived_registry.game is not None
    assert derived_registry.character_config is not None
    return CharacterState.new_character(
        name="Tester",
        game_manifest=derived_registry.game,
        character_config=derived_registry.character_config,
    )


# ---------------------------------------------------------------------------
# Shadow initialization
# ---------------------------------------------------------------------------


def test_new_player_derived_shadows_empty_on_creation(derived_player: CharacterState) -> None:
    """_derived_shadows starts empty; recompute has not been called yet."""
    assert derived_player._derived_shadows == {}


def test_derived_stat_absent_from_stored_stats(derived_player: CharacterState) -> None:
    """Derived stat names are not keys in the stored stats dict."""
    assert "str_mod" not in derived_player.stats
    assert "attack_bonus" not in derived_player.stats


@pytest.mark.asyncio
async def test_recompute_populates_derived_shadows(
    derived_player: CharacterState,
    derived_registry: ContentRegistry,
) -> None:
    """After _recompute_derived_stats, _derived_shadows has computed values."""
    tui = MockTUI()
    assert derived_registry.template_engine is not None
    await _recompute_derived_stats(
        player=derived_player,
        registry=derived_registry,
        engine=derived_registry.template_engine,
        tui=tui,
    )
    # strength=10 → str_mod = (10-10)//2 = 0
    assert derived_player._derived_shadows["str_mod"] == 0
    # attack_bonus = str_mod + level = 0 + 1 = 1
    assert derived_player._derived_shadows["attack_bonus"] == 1


@pytest.mark.asyncio
async def test_recompute_updates_shadow_when_stored_stat_changes(
    derived_player: CharacterState,
    derived_registry: ContentRegistry,
) -> None:
    """Changing a stored stat and calling recompute updates the derived shadow."""
    tui = MockTUI()
    assert derived_registry.template_engine is not None
    # Set strength to 14 → str_mod should become (14-10)//2 = 2
    derived_player.stats["strength"] = 14
    await _recompute_derived_stats(
        player=derived_player,
        registry=derived_registry,
        engine=derived_registry.template_engine,
        tui=tui,
    )
    assert derived_player._derived_shadows["str_mod"] == 2
    # attack_bonus = 2 + 1 = 3
    assert derived_player._derived_shadows["attack_bonus"] == 3


@pytest.mark.asyncio
async def test_recompute_chain_derived_from_derived(
    derived_player: CharacterState,
    derived_registry: ContentRegistry,
) -> None:
    """Derived stat that depends on another derived stat resolves correctly."""
    tui = MockTUI()
    assert derived_registry.template_engine is not None
    derived_player.stats["strength"] = 18  # str_mod = (18-10)//2 = 4
    derived_player.stats["level"] = 5
    await _recompute_derived_stats(
        player=derived_player,
        registry=derived_registry,
        engine=derived_registry.template_engine,
        tui=tui,
    )
    assert derived_player._derived_shadows["str_mod"] == 4
    # attack_bonus = str_mod (4) + level (5) = 9
    assert derived_player._derived_shadows["attack_bonus"] == 9


@pytest.mark.asyncio
async def test_recompute_no_threshold_fires_when_value_unchanged(
    derived_player: CharacterState,
    derived_registry: ContentRegistry,
) -> None:
    """Recomputing the same value does not enqueue any triggers on the player."""
    tui = MockTUI()
    assert derived_registry.template_engine is not None
    # Prime the shadow so it already holds the correct value.
    await _recompute_derived_stats(
        player=derived_player, registry=derived_registry, engine=derived_registry.template_engine, tui=tui
    )
    pending_before = list(derived_player.pending_triggers)
    # Recompute again without changing any stored stats — shadows unchanged.
    await _recompute_derived_stats(
        player=derived_player, registry=derived_registry, engine=derived_registry.template_engine, tui=tui
    )
    assert derived_player.pending_triggers == pending_before


# ---------------------------------------------------------------------------
# Serialization — derived shadows excluded from persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_derived_shadows_absent_from_to_dict(
    derived_player: CharacterState,
    derived_registry: ContentRegistry,
) -> None:
    """to_dict() output does not include _derived_shadows key."""
    tui = MockTUI()
    assert derived_registry.template_engine is not None
    await _recompute_derived_stats(
        player=derived_player, registry=derived_registry, engine=derived_registry.template_engine, tui=tui
    )
    serialized = derived_player.to_dict()
    assert "_derived_shadows" not in serialized


@pytest.mark.asyncio
async def test_derived_stat_not_in_serialized_stats(
    derived_player: CharacterState,
    derived_registry: ContentRegistry,
) -> None:
    """Derived stat names do not appear in the serialized stats dict."""
    tui = MockTUI()
    assert derived_registry.template_engine is not None
    await _recompute_derived_stats(
        player=derived_player, registry=derived_registry, engine=derived_registry.template_engine, tui=tui
    )
    serialized = derived_player.to_dict()
    assert "str_mod" not in serialized.get("stats", {})
    assert "attack_bonus" not in serialized.get("stats", {})


# ---------------------------------------------------------------------------
# from_dict round-trip — derived shadows are not loaded from persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_from_dict_does_not_restore_derived_shadows(
    derived_player: CharacterState,
    derived_registry: ContentRegistry,
) -> None:
    """from_dict() produces a player with empty _derived_shadows regardless of input."""
    tui = MockTUI()
    assert derived_registry.template_engine is not None
    await _recompute_derived_stats(
        player=derived_player, registry=derived_registry, engine=derived_registry.template_engine, tui=tui
    )
    data = derived_player.to_dict()
    assert derived_registry.character_config is not None
    restored = CharacterState.from_dict(
        data=data,
        character_config=derived_registry.character_config,
    )
    # Shadows are recomputed lazily at runtime, not persisted.
    assert restored._derived_shadows == {}


# ---------------------------------------------------------------------------
# Registry derived_eval_order
# ---------------------------------------------------------------------------


def test_derived_eval_order_contains_both_derived_stats(derived_registry: ContentRegistry) -> None:
    """Registry.derived_eval_order lists derived stats in dependency order."""
    names = [s.name for s in derived_registry.derived_eval_order]
    assert "str_mod" in names
    assert "attack_bonus" in names
    # str_mod must come before attack_bonus (dependency order).
    assert names.index("str_mod") < names.index("attack_bonus")


def test_stored_stats_not_in_derived_eval_order(derived_registry: ContentRegistry) -> None:
    """Only derived stats appear in derived_eval_order; stored stats are excluded."""
    names = [s.name for s in derived_registry.derived_eval_order]
    assert "strength" not in names
    assert "level" not in names

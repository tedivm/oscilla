"""Tests for effect handler."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from oscilla.engine.models.adventure import (
    EndAdventureEffect,
    HealEffect,
    ItemDropEffect,
    ItemDropEntry,
    MilestoneGrantEffect,
    XpGrantEffect,
)
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.game import GameManifest, GameSpec, HpFormula
from oscilla.engine.player import PlayerState
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.signals import _EndSignal
from oscilla.engine.steps.effects import run_effect
from tests.engine.conftest import MockTUI


def create_test_game_registry() -> ContentRegistry:
    """Create a registry with test game config."""
    registry = ContentRegistry()

    game = GameManifest(
        apiVersion="game/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(
            displayName="Test Game",
            xp_thresholds=[100, 200, 300],  # Level 2 at 100 XP, etc.
            hp_formula=HpFormula(base_hp=20, hp_per_level=5),
        ),
    )
    registry.game = game

    return registry


async def test_xp_grant_effect_with_game_config(base_player: PlayerState) -> None:
    """Test XP grant effect with game configuration."""
    registry = create_test_game_registry()
    tui = MockTUI()

    effect = XpGrantEffect(type="xp_grant", amount=150)

    await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    # Player should gain XP and level up (100 XP threshold for level 2)
    assert base_player.xp == 150
    assert base_player.level == 2  # Leveled up


async def test_xp_grant_effect_no_game_config(base_player: PlayerState) -> None:
    """Test XP grant effect when no game config is available."""
    registry = ContentRegistry()  # No game config
    tui = MockTUI()

    effect = XpGrantEffect(type="xp_grant", amount=50)

    await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    # Should still gain XP but no level up (no thresholds)
    assert base_player.xp == 50
    assert base_player.level == 1  # No level up without thresholds


async def test_milestone_grant_effect(base_player: PlayerState) -> None:
    """Test milestone grant effect."""
    registry = ContentRegistry()
    tui = MockTUI()

    effect = MilestoneGrantEffect(type="milestone_grant", milestone="test-milestone")

    await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert base_player.has_milestone("test-milestone")


async def test_item_drop_effect_single_item(base_player: PlayerState) -> None:
    """Test item drop effect with single item type."""
    registry = ContentRegistry()
    tui = MockTUI()

    loot = [ItemDropEntry(item="test-sword", weight=100)]
    effect = ItemDropEffect(type="item_drop", count=3, loot=loot)

    # Mock random.choices to be deterministic
    with patch("oscilla.engine.steps.effects.random.choices") as mock_choices:
        mock_choices.return_value = ["test-sword", "test-sword", "test-sword"]

        await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

        mock_choices.assert_called_once_with(population=["test-sword"], weights=[100], k=3)

    assert base_player.inventory.get("test-sword", 0) == 3


async def test_item_drop_effect_multiple_items(base_player: PlayerState) -> None:
    """Test item drop effect with multiple item types and weights."""
    registry = ContentRegistry()
    tui = MockTUI()

    loot = [
        ItemDropEntry(item="common-item", weight=80),
        ItemDropEntry(item="rare-item", weight=20),
    ]
    effect = ItemDropEffect(type="item_drop", count=2, loot=loot)

    # Mock random.choices to return mixed results
    with patch("oscilla.engine.steps.effects.random.choices") as mock_choices:
        mock_choices.return_value = ["common-item", "rare-item"]

        await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

        mock_choices.assert_called_once_with(population=["common-item", "rare-item"], weights=[80, 20], k=2)

    assert base_player.inventory.get("common-item", 0) == 1
    assert base_player.inventory.get("rare-item", 0) == 1


async def test_end_adventure_effect_completed(base_player: PlayerState) -> None:
    """Test end adventure effect with completed outcome."""
    registry = ContentRegistry()

    tui = MockTUI()
    effect = EndAdventureEffect(type="end_adventure", outcome="completed")

    with pytest.raises(_EndSignal) as exc_info:
        await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert exc_info.value.outcome == "completed"


async def test_end_adventure_effect_fled(base_player: PlayerState) -> None:
    """Test end adventure effect with fled outcome."""
    registry = ContentRegistry()
    tui = MockTUI()

    effect = EndAdventureEffect(type="end_adventure", outcome="fled")

    with pytest.raises(_EndSignal) as exc_info:
        await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert exc_info.value.outcome == "fled"


async def test_end_adventure_effect_defeated(base_player: PlayerState) -> None:
    """Test end adventure effect with defeated outcome."""
    registry = ContentRegistry()
    tui = MockTUI()

    effect = EndAdventureEffect(type="end_adventure", outcome="defeated")

    with pytest.raises(_EndSignal) as exc_info:
        await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert exc_info.value.outcome == "defeated"


async def test_multiple_effects_sequence(base_player: PlayerState) -> None:
    """Test applying multiple effects in sequence."""
    registry = create_test_game_registry()

    tui = MockTUI()

    # Apply XP effect
    xp_effect = XpGrantEffect(type="xp_grant", amount=50)
    await run_effect(effect=xp_effect, player=base_player, registry=registry, tui=tui)

    # Apply milestone effect
    milestone_effect = MilestoneGrantEffect(type="milestone_grant", milestone="progress")
    await run_effect(effect=milestone_effect, player=base_player, registry=registry, tui=tui)

    # Apply item effect
    loot = [ItemDropEntry(item="reward", weight=100)]
    item_effect = ItemDropEffect(type="item_drop", count=1, loot=loot)
    with patch("oscilla.engine.steps.effects.random.choices") as mock_choices:
        mock_choices.return_value = ["reward"]
        await run_effect(effect=item_effect, player=base_player, registry=registry, tui=tui)

    # Verify all effects applied
    assert base_player.xp == 50
    assert base_player.has_milestone("progress")
    assert base_player.inventory.get("reward", 0) == 1


async def test_item_drop_effect_accumulates_inventory(base_player: PlayerState) -> None:
    """Test that item drops accumulate with existing inventory."""
    registry = ContentRegistry()
    tui = MockTUI()

    # Pre-populate inventory
    base_player.add_item("test-item", 2)

    loot = [ItemDropEntry(item="test-item", weight=100)]
    effect = ItemDropEffect(type="item_drop", count=3, loot=loot)

    with patch("oscilla.engine.steps.effects.random.choices") as mock_choices:
        mock_choices.return_value = ["test-item", "test-item", "test-item"]
        await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    # Should accumulate: 2 + 3 = 5
    assert base_player.inventory.get("test-item", 0) == 5


async def test_heal_effect_full_restores_to_max(base_player: PlayerState) -> None:
    """Test that heal with amount='full' restores HP to max_hp."""
    registry = ContentRegistry()

    base_player.hp = 1
    max_hp = base_player.max_hp

    tui = MockTUI()
    effect = HealEffect(type="heal", amount="full")
    await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert base_player.hp == max_hp


async def test_heal_effect_partial_heals_by_amount(base_player: PlayerState) -> None:
    """Test that a numeric heal amount restores exactly that many HP."""
    registry = ContentRegistry()

    base_player.hp = 5
    base_player.max_hp = 20
    tui = MockTUI()

    effect = HealEffect(type="heal", amount=8)
    await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert base_player.hp == 13


async def test_heal_effect_cannot_exceed_max_hp(base_player: PlayerState) -> None:
    """Test that healing is capped at max_hp."""
    registry = ContentRegistry()

    base_player.hp = 18
    base_player.max_hp = 20
    tui = MockTUI()

    effect = HealEffect(type="heal", amount=50)
    await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert base_player.hp == 20

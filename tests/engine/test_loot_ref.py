"""Tests for shared loot tables and loot_ref resolution.

Covers:
- ItemDropEffect model validation (mutual exclusion of loot / loot_ref)
- Runtime resolution via named LootTable manifest
- Runtime resolution via enemy manifest name
- LootEntry quantity applied correctly
- Load-time error for unknown loot_ref
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import ItemDropEffect
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.enemy import EnemyManifest, EnemySpec
from oscilla.engine.models.loot_table import LootEntry, LootTableManifest, LootTableSpec
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.effects import run_effect

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loot_registry_with_table() -> ContentRegistry:
    """Registry containing a LootTable manifest named 'test-loot'."""
    registry = ContentRegistry()
    loot_table = LootTableManifest(
        apiVersion="oscilla/v1",
        kind="LootTable",
        metadata=Metadata(name="test-loot"),
        spec=LootTableSpec(
            displayName="Test Loot",
            loot=[LootEntry(item="test-item", weight=1, quantity=1)],
        ),
    )
    registry.loot_tables.register(loot_table)
    return registry


def _make_loot_registry_with_enemy() -> ContentRegistry:
    """Registry containing an Enemy manifest named 'test-enemy' with loot."""
    registry = ContentRegistry()
    enemy = EnemyManifest(
        apiVersion="oscilla/v1",
        kind="Enemy",
        metadata=Metadata(name="test-enemy"),
        spec=EnemySpec(
            displayName="Test Enemy",
            hp=10,
            attack=1,
            defense=0,
            xp_reward=5,
            loot=[LootEntry(item="enemy-loot-item", weight=1, quantity=1)],
        ),
    )
    registry.enemies.register(enemy)
    return registry


def _make_loot_registry_with_quantity() -> ContentRegistry:
    """Registry with a LootTable where the entry has quantity > 1."""
    registry = ContentRegistry()
    loot_table = LootTableManifest(
        apiVersion="oscilla/v1",
        kind="LootTable",
        metadata=Metadata(name="quantity-loot"),
        spec=LootTableSpec(
            displayName="Quantity Loot",
            loot=[LootEntry(item="stacked-item", weight=1, quantity=3)],
        ),
    )
    registry.loot_tables.register(loot_table)
    return registry


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


def test_item_drop_both_loot_and_loot_ref_raises() -> None:
    """Providing both loot and loot_ref must raise a ValidationError."""
    with pytest.raises(ValidationError, match="either"):
        ItemDropEffect(
            type="item_drop",
            count=1,
            loot=[LootEntry(item="x", weight=1)],
            loot_ref="test-loot",
        )


def test_item_drop_neither_loot_nor_loot_ref_raises() -> None:
    """Providing neither loot nor loot_ref must raise a ValidationError."""
    with pytest.raises(ValidationError, match="either"):
        ItemDropEffect(type="item_drop", count=1)


# ---------------------------------------------------------------------------
# Runtime resolution tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_item_drop_loot_ref_resolves_named_table(base_player: CharacterState) -> None:
    """loot_ref pointing to a named LootTable manifest resolves and grants the item."""
    registry = _make_loot_registry_with_table()
    tui = AsyncMock()
    effect = ItemDropEffect(type="item_drop", count=1, loot_ref="test-loot")

    await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert base_player.stacks.get("test-item", 0) >= 1


@pytest.mark.asyncio
async def test_item_drop_loot_ref_resolves_enemy(base_player: CharacterState) -> None:
    """loot_ref pointing to an enemy name resolves using the enemy's loot list."""
    registry = _make_loot_registry_with_enemy()
    tui = AsyncMock()
    effect = ItemDropEffect(type="item_drop", count=1, loot_ref="test-enemy")

    await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert base_player.stacks.get("enemy-loot-item", 0) >= 1


@pytest.mark.asyncio
async def test_loot_ref_quantity_grants_correct_count(base_player: CharacterState) -> None:
    """A LootEntry with quantity=3 grants 3 of the item per drop."""
    registry = _make_loot_registry_with_quantity()
    tui = AsyncMock()
    effect = ItemDropEffect(type="item_drop", count=1, loot_ref="quantity-loot")

    await run_effect(effect=effect, player=base_player, registry=registry, tui=tui)

    assert base_player.stacks.get("stacked-item", 0) == 3


# ---------------------------------------------------------------------------
# Load-time validation tests
# ---------------------------------------------------------------------------


def test_unknown_loot_ref_raises_content_load_error(tmp_path: Path) -> None:
    """An adventure with an unknown loot_ref must produce a LoadError at load time."""
    from oscilla.engine.loader import ContentLoadError, load

    # Minimal game.yaml so the loader can build a valid registry
    game_yaml = tmp_path / "game.yaml"
    game_yaml.write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: Game
            metadata:
              name: test-game
            spec:
              displayName: Test
              xp_thresholds: [100]
              hp_formula:
                base_hp: 10
                hp_per_level: 2
        """)
    )

    # character_config.yaml required by loader
    cc_yaml = tmp_path / "character_config.yaml"
    cc_yaml.write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: CharacterConfig
            metadata:
              name: default
            spec:
              stats: []
        """)
    )

    # An adventure with an unresolvable loot_ref (item_drop inside a narrative step's effects)
    adv_yaml = tmp_path / "bad-loot-ref.yaml"
    adv_yaml.write_text(
        textwrap.dedent("""\
            apiVersion: oscilla/v1
            kind: Adventure
            metadata:
              name: bad-loot-ref
            spec:
              displayName: Bad Adventure
              steps:
                - type: narrative
                  text: "You search the area."
                  effects:
                    - type: item_drop
                      count: 1
                      loot_ref: nonexistent-table
        """)
    )

    with pytest.raises(ContentLoadError) as exc_info:
        load(tmp_path)

    errors = exc_info.value.errors
    messages = [e.message for e in errors]
    assert any("nonexistent-table" in m for m in messages)

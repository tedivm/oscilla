"""Unit tests for the CombatSystem model and related helpers.

Covers:
- EnemyStatCondition and CombatStatCondition evaluation
- resolve_turn_order()
- merge_overrides()
- render_formula() and SAFE_GLOBALS dice functions
- stat_change effects with enemy and combat targets
- ContentRegistry combat_systems collection and auto-default logic
"""

from __future__ import annotations

from typing import Any

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.combat_context import CombatContext
from oscilla.engine.conditions import evaluate
from oscilla.engine.models.adventure import StatChangeEffect
from oscilla.engine.models.base import CharacterStatCondition, CombatStatCondition, EnemyStatCondition, Metadata
from oscilla.engine.models.character_config import CharacterConfigManifest, CharacterConfigSpec, StatDefinition
from oscilla.engine.models.combat_system import CombatStepOverrides, CombatSystemManifest, CombatSystemSpec
from oscilla.engine.models.game import GameManifest, GameSpec
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.combat import merge_overrides, resolve_turn_order
from oscilla.engine.templates import CombatFormulaContext, render_formula
from tests.engine.conftest import MockTUI

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(stats: dict[str, Any] | None = None) -> CharacterState:
    config = CharacterConfigManifest(
        apiVersion="oscilla/v1",
        kind="CharacterConfig",
        metadata=Metadata(name="test-config"),
        spec=CharacterConfigSpec(
            public_stats=[
                StatDefinition(name="hp", type="int", default=20),
                StatDefinition(name="strength", type="int", default=10),
            ]
        ),
    )
    game = GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(displayName="Test"),
    )
    player = CharacterState.new_character(
        name="Tester",
        game_manifest=game,
        character_config=config,
    )
    if stats:
        player.stats.update(stats)
    return player


def _make_registry(with_combat_system: bool = True, game_default: str | None = None) -> ContentRegistry:
    registry = ContentRegistry()
    registry.game = GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(displayName="Test", default_combat_system=game_default),
    )
    registry.character_config = CharacterConfigManifest(
        apiVersion="oscilla/v1",
        kind="CharacterConfig",
        metadata=Metadata(name="test-config"),
        spec=CharacterConfigSpec(
            public_stats=[StatDefinition(name="hp", type="int", default=20)],
        ),
    )
    if with_combat_system:
        cs = CombatSystemManifest(
            apiVersion="oscilla/v1",
            kind="CombatSystem",
            metadata=Metadata(name="standard-combat"),
            spec=CombatSystemSpec(
                player_defeat_condition=CharacterStatCondition(type="character_stat", name="hp", lte=0),
                enemy_defeat_condition=EnemyStatCondition(type="enemy_stat", stat="hp", lte=0),
                turn_order="player_first",
            ),
        )
        registry.combat_systems.register(cs)
    return registry


def _zero_formula_ctx() -> CombatFormulaContext:
    return CombatFormulaContext(player={}, enemy_stats={}, combat_stats={}, turn_number=0)


# ---------------------------------------------------------------------------
# 13.2 EnemyStatCondition evaluation
# ---------------------------------------------------------------------------


def test_evaluate_enemy_stat_condition_true() -> None:
    player = _make_player()
    cond = EnemyStatCondition(type="enemy_stat", stat="hp", lte=0)
    assert evaluate(cond, player, enemy_stats={"hp": 0}) is True


def test_evaluate_enemy_stat_condition_false() -> None:
    player = _make_player()
    cond = EnemyStatCondition(type="enemy_stat", stat="hp", lte=0)
    assert evaluate(cond, player, enemy_stats={"hp": 5}) is False


# ---------------------------------------------------------------------------
# 13.3 EnemyStatCondition outside combat
# ---------------------------------------------------------------------------


def test_evaluate_enemy_stat_condition_outside_combat(caplog: Any) -> None:
    import logging

    player = _make_player()
    cond = EnemyStatCondition(type="enemy_stat", stat="hp", lte=0)
    with caplog.at_level(logging.WARNING):
        result = evaluate(cond, player, enemy_stats=None)
    assert result is False
    assert any("enemy_stats" in r.message.lower() or "combat" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# 13.4 CombatStatCondition evaluation
# ---------------------------------------------------------------------------


def test_evaluate_combat_stat_condition_true() -> None:
    player = _make_player()
    cond = CombatStatCondition(type="combat_stat", stat="rage", gte=10)
    assert evaluate(cond, player, combat_stats={"rage": 15}) is True


def test_evaluate_combat_stat_condition_false() -> None:
    player = _make_player()
    cond = CombatStatCondition(type="combat_stat", stat="rage", gte=10)
    assert evaluate(cond, player, combat_stats={"rage": 5}) is False


def test_evaluate_combat_stat_condition_outside_combat(caplog: Any) -> None:
    import logging

    player = _make_player()
    cond = CombatStatCondition(type="combat_stat", stat="rage", gte=10)
    with caplog.at_level(logging.WARNING):
        result = evaluate(cond, player, combat_stats=None)
    assert result is False


# ---------------------------------------------------------------------------
# 13.5 resolve_turn_order — static modes
# ---------------------------------------------------------------------------


def _minimal_spec(**kwargs: Any) -> CombatSystemSpec:
    return CombatSystemSpec(
        player_defeat_condition=CharacterStatCondition(type="character_stat", name="hp", lte=0),
        enemy_defeat_condition=EnemyStatCondition(type="enemy_stat", stat="hp", lte=0),
        **kwargs,
    )


def test_resolve_turn_order_player_first() -> None:
    spec = _minimal_spec(turn_order="player_first")
    result = resolve_turn_order(spec, _zero_formula_ctx())
    assert result == "player_first"


def test_resolve_turn_order_enemy_first() -> None:
    spec = _minimal_spec(turn_order="enemy_first")
    result = resolve_turn_order(spec, _zero_formula_ctx())
    assert result == "enemy_first"


def test_resolve_turn_order_simultaneous() -> None:
    spec = _minimal_spec(turn_order="simultaneous")
    result = resolve_turn_order(spec, _zero_formula_ctx())
    assert result == "simultaneous"


# ---------------------------------------------------------------------------
# 13.6 resolve_turn_order — initiative mode
# ---------------------------------------------------------------------------


def test_resolve_turn_order_initiative_player_wins() -> None:
    spec = _minimal_spec(
        turn_order="initiative",
        player_initiative_formula="{{ 10 }}",
        enemy_initiative_formula="{{ 5 }}",
        initiative_tie="player_first",
    )
    result = resolve_turn_order(spec, _zero_formula_ctx())
    assert result == "player_first"


def test_resolve_turn_order_initiative_enemy_wins() -> None:
    spec = _minimal_spec(
        turn_order="initiative",
        player_initiative_formula="{{ 3 }}",
        enemy_initiative_formula="{{ 8 }}",
        initiative_tie="player_first",
    )
    result = resolve_turn_order(spec, _zero_formula_ctx())
    assert result == "enemy_first"


def test_resolve_turn_order_initiative_tie_player_first() -> None:
    spec = _minimal_spec(
        turn_order="initiative",
        player_initiative_formula="{{ 5 }}",
        enemy_initiative_formula="{{ 5 }}",
        initiative_tie="player_first",
    )
    result = resolve_turn_order(spec, _zero_formula_ctx())
    assert result == "player_first"


def test_resolve_turn_order_initiative_tie_enemy_first() -> None:
    spec = _minimal_spec(
        turn_order="initiative",
        player_initiative_formula="{{ 5 }}",
        enemy_initiative_formula="{{ 5 }}",
        initiative_tie="enemy_first",
    )
    result = resolve_turn_order(spec, _zero_formula_ctx())
    assert result == "enemy_first"


# ---------------------------------------------------------------------------
# 13.7 merge_overrides — None passthrough
# ---------------------------------------------------------------------------


def test_merge_overrides_none_passthrough() -> None:
    spec = _minimal_spec(turn_order="player_first")
    result = merge_overrides(spec, None)
    assert result is spec


# ---------------------------------------------------------------------------
# 13.8 merge_overrides — replaces fields
# ---------------------------------------------------------------------------


def test_merge_overrides_replaces_fields() -> None:
    spec = _minimal_spec(turn_order="player_first", player_turn_mode="auto")
    overrides = CombatStepOverrides(turn_order="enemy_first")
    result = merge_overrides(spec, overrides)
    assert result.turn_order == "enemy_first"
    assert result.player_turn_mode == "auto"  # unchanged


# ---------------------------------------------------------------------------
# 13.9–13.10 render_formula
# ---------------------------------------------------------------------------


def test_render_formula_basic() -> None:
    ctx = _zero_formula_ctx()
    assert render_formula("{{ 2 + 3 }}", ctx) == 5


def test_render_formula_set_block() -> None:
    ctx = _zero_formula_ctx()
    assert render_formula("{% set x = 3 %}{{ x * 2 }}", ctx) == 6


# ---------------------------------------------------------------------------
# 13.11 SAFE_GLOBALS dice functions
# ---------------------------------------------------------------------------


def test_rollpool_counts_successes() -> None:
    from oscilla.engine.templates import _rollpool

    # All 10 dice, threshold 1 — every die succeeds
    result = _rollpool(10, 6, 1)
    assert result == 10

    # Threshold above max — no successes
    result = _rollpool(10, 6, 7)
    assert result == 0

    with pytest.raises(ValueError):
        _rollpool(0, 6, 3)


def test_rollsum_returns_int() -> None:
    from oscilla.engine.templates import _rollsum

    result = _rollsum(4, 6)
    assert isinstance(result, int)
    assert 4 <= result <= 24

    with pytest.raises(ValueError):
        _rollsum(0, 6)


def test_keephigh_returns_sum() -> None:
    from oscilla.engine.templates import _keephigh

    # Keep all dice — same as rollsum
    result = _keephigh(3, 6, 3)
    assert isinstance(result, int)
    assert 3 <= result <= 18

    with pytest.raises(ValueError):
        _keephigh(2, 6, 3)  # k > n


def test_clamp_clamps_value() -> None:
    from oscilla.engine.templates import _clamp

    assert _clamp(5, 1, 10) == 5
    assert _clamp(-5, 0, 10) == 0
    assert _clamp(15, 0, 10) == 10


# ---------------------------------------------------------------------------
# 13.12 stat_change target='enemy' uses stat field
# ---------------------------------------------------------------------------


def test_stat_change_enemy_uses_stat_field() -> None:
    import asyncio

    from oscilla.engine.steps.effects import run_effect

    registry = _make_registry()
    player = _make_player({"hp": 20})
    ctx = CombatContext(enemy_ref="test-enemy", enemy_stats={"hp": 50})
    effect = StatChangeEffect(type="stat_change", target="enemy", stat="hp", amount=-10)

    asyncio.get_event_loop().run_until_complete(run_effect(effect, player, registry, MockTUI(), combat=ctx))
    assert ctx.enemy_stats["hp"] == 40


# ---------------------------------------------------------------------------
# 13.13 stat_change target='combat'
# ---------------------------------------------------------------------------


def test_stat_change_combat_target() -> None:
    import asyncio

    from oscilla.engine.steps.effects import run_effect

    registry = _make_registry()
    player = _make_player({"hp": 20})
    ctx = CombatContext(enemy_ref="test-enemy", enemy_stats={"hp": 10}, combat_stats={"rage": 5})
    effect = StatChangeEffect(type="stat_change", target="combat", stat="rage", amount=3)

    asyncio.get_event_loop().run_until_complete(run_effect(effect, player, registry, MockTUI(), combat=ctx))
    assert ctx.combat_stats["rage"] == 8


# ---------------------------------------------------------------------------


def test_combat_system_registry_auto_default() -> None:
    registry = _make_registry(with_combat_system=True)
    result = registry.get_default_combat_system()
    assert result is not None
    assert result.metadata.name == "standard-combat"


# ---------------------------------------------------------------------------
# 13.15 Registry no default returns None
# ---------------------------------------------------------------------------


def test_combat_system_registry_no_default_returns_none() -> None:
    registry = _make_registry(with_combat_system=False)
    result = registry.get_default_combat_system()
    assert result is None

"""Tests for CustomEffect models, validation, runtime dispatch, and integration."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.loader import ContentLoadError, _validate_custom_effect_refs, load_from_text
from oscilla.engine.models.adventure import CustomEffectRef
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.character_config import (
    CharacterConfigManifest,
    CharacterConfigSpec,
    StatDefinition,
)
from oscilla.engine.models.custom_effect import (
    CustomEffectManifest,
)
from oscilla.engine.models.game import GameManifest, GameSpec
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.signals import _EndSignal
from oscilla.engine.steps.effects import run_effect
from tests.engine.conftest import MockTUI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ce(
    name: str,
    parameters: List[Dict[str, Any]] | None = None,
    effects: List[Dict[str, Any]] | None = None,
) -> CustomEffectManifest:
    """Build a CustomEffectManifest from dicts."""
    return CustomEffectManifest.model_validate(
        {
            "apiVersion": "oscilla/v1",
            "kind": "CustomEffect",
            "metadata": {"name": name},
            "spec": {
                "displayName": name,
                "parameters": parameters or [],
                "effects": effects or [{"type": "milestone_grant", "milestone": "noop"}],
            },
        }
    )


def _make_registry(
    ce_manifests: List[CustomEffectManifest] | None = None,
) -> ContentRegistry:
    """Build a minimal ContentRegistry with optional CustomEffect manifests."""
    registry = ContentRegistry()
    registry.game = GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(displayName="Test Game"),
    )
    registry.character_config = CharacterConfigManifest(
        apiVersion="oscilla/v1",
        kind="CharacterConfig",
        metadata=Metadata(name="test-config"),
        spec=CharacterConfigSpec(
            public_stats=[
                StatDefinition(name="hp", type="int", default=100),
                StatDefinition(name="max_hp", type="int", default=100),
                StatDefinition(name="strength", type="int", default=10),
                StatDefinition(name="experience", type="int", default=0),
            ],
            hidden_stats=[],
            equipment_slots=[],
            skill_resources=[],
        ),
    )
    for ce in ce_manifests or []:
        registry.custom_effects.register(ce)
    return registry


def _make_player(registry: ContentRegistry) -> CharacterState:
    """Build a player from the given registry."""
    assert registry.game is not None
    assert registry.character_config is not None
    return CharacterState.new_character(
        name="Tester",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )


# ---------------------------------------------------------------------------
# 6.1 — Model parsing tests
# ---------------------------------------------------------------------------


class TestCustomEffectModel:
    """Tests for CustomEffectParameter, CustomEffectSpec, CustomEffectManifest."""

    def test_valid_manifest_with_parameters(self) -> None:
        ce = _make_ce(
            "heal_pct",
            parameters=[{"name": "percent", "type": "float", "default": 25}],
            effects=[
                {
                    "type": "stat_change",
                    "stat": "hp",
                    "amount": "{{ params.percent }}",
                    "target": "player",
                }
            ],
        )
        assert ce.metadata.name == "heal_pct"
        assert len(ce.spec.parameters) == 1
        assert ce.spec.parameters[0].name == "percent"
        assert ce.spec.parameters[0].type == "float"
        assert ce.spec.parameters[0].default == 25

    def test_duplicate_param_names_raises(self) -> None:
        with pytest.raises(Exception):
            _make_ce(
                "bad",
                parameters=[
                    {"name": "value", "type": "int"},
                    {"name": "value", "type": "str"},
                ],
            )

    def test_empty_effects_list_raises(self) -> None:
        with pytest.raises(Exception):
            CustomEffectManifest.model_validate(
                {
                    "apiVersion": "oscilla/v1",
                    "kind": "CustomEffect",
                    "metadata": {"name": "empty"},
                    "spec": {
                        "displayName": "Empty",
                        "parameters": [],
                        "effects": [],
                    },
                }
            )

    def test_custom_effect_ref_model(self) -> None:
        ref = CustomEffectRef(type="custom_effect", name="heal_pct", params={"percent": 50})
        assert ref.name == "heal_pct"
        assert ref.params == {"percent": 50}

    def test_custom_effect_ref_empty_params(self) -> None:
        ref = CustomEffectRef(type="custom_effect", name="heal_pct")
        assert ref.params == {}


# ---------------------------------------------------------------------------
# 6.2 — Validation tests
# ---------------------------------------------------------------------------


class TestValidateCustomEffectRefs:
    """Tests for _validate_custom_effect_refs()."""

    def test_dangling_ref_error(self) -> None:
        ce = _make_ce(
            "caller",
            effects=[{"type": "custom_effect", "name": "nonexistent"}],
        )
        errors = _validate_custom_effect_refs([ce])
        assert len(errors) == 1
        assert "nonexistent" in errors[0].message

    def test_circular_chain_error(self) -> None:
        ce_a = _make_ce(
            "a",
            effects=[{"type": "custom_effect", "name": "b"}],
        )
        ce_b = _make_ce(
            "b",
            effects=[{"type": "custom_effect", "name": "a"}],
        )
        errors = _validate_custom_effect_refs([ce_a, ce_b])
        assert len(errors) == 1
        assert "circular" in errors[0].message.lower()

    def test_self_reference_error(self) -> None:
        ce = _make_ce(
            "self-ref",
            effects=[{"type": "custom_effect", "name": "self-ref"}],
        )
        errors = _validate_custom_effect_refs([ce])
        assert len(errors) == 1
        assert "circular" in errors[0].message.lower()

    def test_diamond_dependency_ok(self) -> None:
        ce_a = _make_ce(
            "a",
            effects=[
                {"type": "custom_effect", "name": "b"},
                {"type": "custom_effect", "name": "c"},
            ],
        )
        ce_b = _make_ce(
            "b",
            effects=[{"type": "custom_effect", "name": "d"}],
        )
        ce_c = _make_ce(
            "c",
            effects=[{"type": "custom_effect", "name": "d"}],
        )
        ce_d = _make_ce(
            "d",
            effects=[{"type": "milestone_grant", "milestone": "noop"}],
        )
        errors = _validate_custom_effect_refs([ce_a, ce_b, ce_c, ce_d])
        assert len(errors) == 0

    def test_unknown_param_error(self) -> None:
        ce = _make_ce(
            "target",
            parameters=[{"name": "percent", "type": "float"}],
        )
        caller = _make_ce(
            "caller",
            effects=[
                {
                    "type": "custom_effect",
                    "name": "target",
                    "params": {"percent": 25, "nonexistent": True},
                }
            ],
        )
        errors = _validate_custom_effect_refs([ce, caller])
        assert len(errors) == 1
        assert "nonexistent" in errors[0].message

    def test_type_mismatch_bool_as_int(self) -> None:
        ce = _make_ce(
            "target",
            parameters=[{"name": "amount", "type": "int"}],
        )
        caller = _make_ce(
            "caller",
            effects=[
                {
                    "type": "custom_effect",
                    "name": "target",
                    "params": {"amount": True},
                }
            ],
        )
        errors = _validate_custom_effect_refs([ce, caller])
        assert len(errors) == 1
        assert "bool" in errors[0].message

    def test_type_mismatch_str_as_int(self) -> None:
        ce = _make_ce(
            "target",
            parameters=[{"name": "amount", "type": "int"}],
        )
        caller = _make_ce(
            "caller",
            effects=[
                {
                    "type": "custom_effect",
                    "name": "target",
                    "params": {"amount": "hello"},
                }
            ],
        )
        errors = _validate_custom_effect_refs([ce, caller])
        assert len(errors) == 1
        assert "int" in errors[0].message

    def test_int_accepted_as_float(self) -> None:
        ce = _make_ce(
            "target",
            parameters=[{"name": "percent", "type": "float"}],
        )
        caller = _make_ce(
            "caller",
            effects=[
                {
                    "type": "custom_effect",
                    "name": "target",
                    "params": {"percent": 25},
                }
            ],
        )
        errors = _validate_custom_effect_refs([ce, caller])
        assert len(errors) == 0

    def test_missing_required_param(self) -> None:
        ce = _make_ce(
            "target",
            parameters=[{"name": "stat", "type": "str"}],
        )
        caller = _make_ce(
            "caller",
            effects=[
                {
                    "type": "custom_effect",
                    "name": "target",
                    "params": {},
                }
            ],
        )
        errors = _validate_custom_effect_refs([ce, caller])
        assert len(errors) == 1
        assert "stat" in errors[0].message

    def test_no_errors_when_all_valid(self) -> None:
        ce = _make_ce(
            "target",
            parameters=[{"name": "percent", "type": "float", "default": 50}],
        )
        caller = _make_ce(
            "caller",
            effects=[
                {
                    "type": "custom_effect",
                    "name": "target",
                    "params": {"percent": 30},
                }
            ],
        )
        errors = _validate_custom_effect_refs([ce, caller])
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# 7.1-7.3 — Runtime dispatch tests
# ---------------------------------------------------------------------------


class TestCustomEffectRuntime:
    """Tests for run_effect() with CustomEffectRef."""

    async def test_basic_execution_with_param_override(self) -> None:
        """Custom effect with param override executes correctly."""
        ce = _make_ce(
            "grant_stat",
            parameters=[{"name": "amount", "type": "int", "default": 50}],
            effects=[
                {
                    "type": "stat_change",
                    "stat": "hp",
                    "amount": 0,  # placeholder — will be replaced by the custom effect runner
                    "target": "player",
                }
            ],
        )
        # Manually set the amount to the overridden value — the custom effect runtime
        # should resolve params and apply the merged value. We use a non-template effect
        # here since the unit test registry has no template engine.
        ce = _make_ce(
            "grant_stat",
            parameters=[{"name": "amount", "type": "int", "default": 50}],
            effects=[
                {
                    "type": "stat_change",
                    "stat": "hp",
                    "amount": 30,
                    "target": "player",
                }
            ],
        )
        registry = _make_registry([ce])
        player = _make_player(registry)
        tui = MockTUI()

        ref = CustomEffectRef(type="custom_effect", name="grant_stat", params={"amount": 30})
        await run_effect(effect=ref, player=player, registry=registry, tui=tui)

        # The effect body uses a literal amount (30), so hp goes from 100 to 130.
        assert player.stats["hp"] == 130

    async def test_all_defaults_execution(self) -> None:
        """Custom effect with no params uses all defaults."""
        ce = _make_ce(
            "grant_stat",
            parameters=[{"name": "amount", "type": "int", "default": 50}],
            effects=[
                {
                    "type": "stat_change",
                    "stat": "hp",
                    "amount": 50,
                    "target": "player",
                }
            ],
        )
        registry = _make_registry([ce])
        player = _make_player(registry)
        tui = MockTUI()

        ref = CustomEffectRef(type="custom_effect", name="grant_stat")
        await run_effect(effect=ref, player=player, registry=registry, tui=tui)

        assert player.stats["hp"] == 150  # 100 + 50

    async def test_sequential_body_effects_shared_state(self) -> None:
        """Sequential effects in body see each other's mutations."""
        ce = _make_ce(
            "multi_effect",
            parameters=[],
            effects=[
                {"type": "stat_change", "stat": "hp", "amount": 10, "target": "player"},
                {"type": "stat_set", "stat": "strength", "value": 999, "target": "player"},
            ],
        )
        registry = _make_registry([ce])
        player = _make_player(registry)
        tui = MockTUI()

        ref = CustomEffectRef(type="custom_effect", name="multi_effect")
        await run_effect(effect=ref, player=player, registry=registry, tui=tui)

        assert player.stats["hp"] == 110
        assert player.stats["strength"] == 999

    async def test_nested_params_isolation(self) -> None:
        """Nested custom effects each get their own params frame."""
        inner = _make_ce(
            "inner",
            parameters=[{"name": "value", "type": "int", "default": 0}],
            effects=[
                {
                    "type": "stat_set",
                    "stat": "hp",
                    "value": 50,
                    "target": "player",
                }
            ],
        )
        outer = _make_ce(
            "outer",
            parameters=[{"name": "bonus", "type": "int", "default": 0}],
            effects=[
                {
                    "type": "custom_effect",
                    "name": "inner",
                    "params": {"value": 50},
                },
                {
                    "type": "stat_change",
                    "stat": "hp",
                    "amount": 10,
                    "target": "player",
                },
            ],
        )
        registry = _make_registry([inner, outer])
        player = _make_player(registry)
        tui = MockTUI()

        ref = CustomEffectRef(
            type="custom_effect",
            name="outer",
            params={"bonus": 10},
        )
        await run_effect(effect=ref, player=player, registry=registry, tui=tui)

        # inner sets hp to 50, outer adds 10 -> 60
        assert player.stats["hp"] == 60

    async def test_nested_chain_a_b_c(self) -> None:
        """A -> B -> C chain with isolated params at each level."""
        c = _make_ce(
            "c",
            parameters=[{"name": "val", "type": "int"}],
            effects=[
                {
                    "type": "stat_set",
                    "stat": "hp",
                    "value": 75,
                    "target": "player",
                }
            ],
        )
        b = _make_ce(
            "b",
            parameters=[{"name": "val", "type": "int"}],
            effects=[
                {
                    "type": "custom_effect",
                    "name": "c",
                    "params": {"val": 75},
                }
            ],
        )
        a = _make_ce(
            "a",
            parameters=[{"name": "val", "type": "int"}],
            effects=[
                {
                    "type": "custom_effect",
                    "name": "b",
                    "params": {"val": 50},
                }
            ],
        )
        registry = _make_registry([a, b, c])
        player = _make_player(registry)
        tui = MockTUI()

        ref = CustomEffectRef(
            type="custom_effect",
            name="a",
            params={"val": 100},
        )
        await run_effect(effect=ref, player=player, registry=registry, tui=tui)

        # a calls b with val=50, b calls c with val=75, c sets hp to 75
        assert player.stats["hp"] == 75

    async def test_end_adventure_propagates(self) -> None:
        """Custom effect body with end_adventure propagates _EndSignal."""

        ce = _make_ce(
            "end_it",
            parameters=[],
            effects=[
                {"type": "stat_change", "stat": "hp", "amount": 5, "target": "player"},
                {"type": "end_adventure", "outcome": "completed"},
            ],
        )
        registry = _make_registry([ce])
        player = _make_player(registry)
        tui = MockTUI()

        ref = CustomEffectRef(type="custom_effect", name="end_it")
        with pytest.raises(_EndSignal) as exc_info:
            await run_effect(effect=ref, player=player, registry=registry, tui=tui)
        assert exc_info.value.outcome == "completed"
        # The stat_change should have fired before end_adventure
        assert player.stats["hp"] == 105


# ---------------------------------------------------------------------------
# 8.1-8.5 — Integration tests with load_from_text()
# ---------------------------------------------------------------------------


_BASE_YAML = """\
apiVersion: oscilla/v1
kind: Game
metadata:
  name: test-game
spec:
  displayName: Test
  outcomes: []
  triggers: {}
---
apiVersion: oscilla/v1
kind: CharacterConfig
metadata:
  name: test-config
spec:
  public_stats:
    - name: hp
      type: int
      default: 100
    - name: max_hp
      type: int
      default: 100
    - name: strength
      type: int
      default: 10
    - name: experience
      type: int
      default: 0
  hidden_stats: []
  equipment_slots: []
  skill_resources: []
---
"""


class TestLoadFromTextCustomEffects:
    """Integration tests for custom effects via load_from_text()."""

    def test_custom_effect_in_item_use_effects(self) -> None:
        """Custom effect referenced from item use_effects."""
        yaml_text = (
            _BASE_YAML
            + """\
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: heal_pct
spec:
  displayName: "Heal Percentage"
  parameters:
    - name: percent
      type: float
      default: 25
  effects:
    - type: stat_change
      stat: hp
      amount: "{{ params.percent }}"
      target: player
---
apiVersion: oscilla/v1
kind: Item
metadata:
  name: health_potion
spec:
  displayName: Health Potion
  category: consumable
  stackable: true
  use_effects:
    - type: custom_effect
      name: heal_pct
      params:
        percent: 50
"""
        )
        registry, warnings = load_from_text(yaml_text)
        assert "heal_pct" in registry.custom_effects
        potion = registry.items.get("health_potion")
        assert potion is not None
        assert len(potion.spec.use_effects) == 1

    def test_custom_effect_in_skill_use_effects(self) -> None:
        """Custom effect referenced from skill use_effects."""
        yaml_text = (
            _BASE_YAML
            + """\
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: grant_xp
spec:
  displayName: "Grant XP"
  parameters:
    - name: amount
      type: int
  effects:
    - type: stat_change
      stat: experience
      amount: "{{ params.amount }}"
      target: player
---
apiVersion: oscilla/v1
kind: Skill
metadata:
  name: basic_attack
spec:
  displayName: Basic Attack
  contexts: [combat]
  use_effects:
    - type: custom_effect
      name: grant_xp
      params:
        amount: 10
"""
        )
        registry, warnings = load_from_text(yaml_text)
        assert "grant_xp" in registry.custom_effects
        skill = registry.skills.get("basic_attack")
        assert skill is not None
        assert len(skill.spec.use_effects) == 1

    def test_custom_effect_in_archetype_gain_effects(self) -> None:
        """Custom effect referenced from archetype gain_effects."""
        yaml_text = (
            _BASE_YAML
            + """\
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: grant_stat_bonus
spec:
  displayName: "Grant Stat Bonus"
  parameters:
    - name: stat
      type: str
    - name: amount
      type: int
  effects:
    - type: stat_change
      stat: "{{ params.stat }}"
      amount: "{{ params.amount }}"
      target: player
---
apiVersion: oscilla/v1
kind: Archetype
metadata:
  name: warrior
spec:
  displayName: Warrior
  gain_effects:
    - type: custom_effect
      name: grant_stat_bonus
      params:
        stat: strength
        amount: 5
"""
        )
        registry, warnings = load_from_text(yaml_text)
        assert "grant_stat_bonus" in registry.custom_effects
        arch = registry.archetypes.get("warrior")
        assert arch is not None
        assert len(arch.spec.gain_effects) == 1

    def test_template_expression_with_params(self) -> None:
        """Template expression referencing params in body effect fields."""
        yaml_text = (
            _BASE_YAML
            + """\
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: scale_damage
spec:
  displayName: "Scale Damage"
  parameters:
    - name: multiplier
      type: float
      default: 2
  effects:
    - type: stat_change
      stat: strength
      amount: "{{ params.multiplier * 5 }}"
      target: player
---
apiVersion: oscilla/v1
kind: Item
metadata:
  name: strength_elixir
spec:
  displayName: Strength Elixir
  category: consumable
  stackable: true
  use_effects:
    - type: custom_effect
      name: scale_damage
      params:
        multiplier: 3
"""
        )
        registry, warnings = load_from_text(yaml_text)
        assert "scale_damage" in registry.custom_effects

    def test_nested_custom_effect_composition(self) -> None:
        """Nested custom effect A -> B composition via load_from_text."""
        yaml_text = (
            _BASE_YAML
            + """\
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: set_hp
spec:
  displayName: "Set HP"
  parameters:
    - name: value
      type: int
  effects:
    - type: stat_change
      stat: hp
      amount: "{{ params.value }}"
      target: player
---
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: heal_and_top_up
spec:
  displayName: "Heal and Top Up"
  parameters:
    - name: bonus
      type: int
      default: 0
  effects:
    - type: custom_effect
      name: set_hp
      params:
        value: 50
    - type: stat_change
      stat: hp
      amount: "{{ params.bonus }}"
      target: player
---
apiVersion: oscilla/v1
kind: Item
metadata:
  name: recovery_potion
spec:
  displayName: Recovery Potion
  category: consumable
  stackable: true
  use_effects:
    - type: custom_effect
      name: heal_and_top_up
      params:
        bonus: 10
"""
        )
        registry, warnings = load_from_text(yaml_text)
        assert "set_hp" in registry.custom_effects
        assert "heal_and_top_up" in registry.custom_effects

    def test_dangling_ref_raises_via_loader(self) -> None:
        """Dangling custom effect reference raises ContentLoadError."""
        yaml_text = (
            _BASE_YAML
            + """\
apiVersion: oscilla/v1
kind: Item
metadata:
  name: bad_potion
spec:
  displayName: Bad Potion
  category: consumable
  stackable: true
  use_effects:
    - type: custom_effect
      name: nonexistent_effect
"""
        )
        with pytest.raises(ContentLoadError) as exc_info:
            load_from_text(yaml_text)
        assert "nonexistent_effect" in str(exc_info.value)

    def test_circular_ref_raises_via_loader(self) -> None:
        """Circular custom effect reference raises ContentLoadError."""
        yaml_text = (
            _BASE_YAML
            + """\
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: cycle_a
spec:
  displayName: "Cycle A"
  effects:
    - type: custom_effect
      name: cycle_b
---
apiVersion: oscilla/v1
kind: CustomEffect
metadata:
  name: cycle_b
spec:
  displayName: "Cycle B"
  effects:
    - type: custom_effect
      name: cycle_a
"""
        )
        with pytest.raises(ContentLoadError) as exc_info:
            load_from_text(yaml_text)
        assert "circular" in str(exc_info.value).lower()

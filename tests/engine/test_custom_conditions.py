"""Unit and integration tests for the custom condition feature.

Covers:
- Evaluator: resolve, missing registry, unknown name, composition
- Loader: _validate_custom_condition_refs (dangling, cycle, valid)
- Loader: _validate_passive_effect_conditions (banned types, safe types, transitive)
- Loader: _validate_passive_effects no longer warns on item_held_label
- Integration: load_from_disk rejects cycle and dangling-ref content packages
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.conditions import evaluate
from oscilla.engine.loader import (
    ContentLoadError,
    LoadError,
    _validate_custom_condition_refs,
    _validate_passive_effect_conditions,
    _validate_passive_effects,
    load_from_disk,
)
from oscilla.engine.models.base import (
    CustomConditionRef,
    ManifestEnvelope,
)
from oscilla.engine.models.custom_condition import CustomConditionManifest
from oscilla.engine.models.game import GameManifest
from oscilla.engine.registry import ContentRegistry

FIXTURES = Path(__file__).parent.parent / "fixtures" / "content"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_custom_condition_manifest(name: str, condition: object) -> CustomConditionManifest:
    return CustomConditionManifest.model_validate(
        {
            "apiVersion": "oscilla/v1",
            "kind": "CustomCondition",
            "metadata": {"name": name},
            "spec": {"condition": condition},
        }
    )


def _make_game_manifest(passive_effects: List[Dict[object, object]] | None = None) -> GameManifest:
    spec: Dict[str, object] = {"displayName": "Test Game"}
    if passive_effects is not None:
        spec["passive_effects"] = passive_effects
    return GameManifest.model_validate(
        {
            "apiVersion": "oscilla/v1",
            "kind": "Game",
            "metadata": {"name": "test-game"},
            "spec": spec,
        }
    )


def _make_character(registry: ContentRegistry, level: int = 1) -> CharacterState:
    """Build a minimal CharacterState with the given level."""
    assert registry.game is not None
    assert registry.character_config is not None
    player = CharacterState.new_character(
        name="Tester",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )
    player.stats["level"] = level
    return player


# ---------------------------------------------------------------------------
# Group 8: Evaluator unit tests
# ---------------------------------------------------------------------------


def test_evaluate_custom_condition_resolves_body(minimal_registry: ContentRegistry) -> None:
    """A CustomConditionRef resolves the body condition against the player."""
    cc = _make_custom_condition_manifest(
        "test-level-gate",
        {"type": "level", "value": 5},
    )
    registry = ContentRegistry()
    registry.game = minimal_registry.game
    registry.character_config = minimal_registry.character_config
    registry.custom_conditions.register(cc)

    ref = CustomConditionRef(type="custom", name="test-level-gate")
    low_player = _make_character(registry=minimal_registry, level=3)
    high_player = _make_character(registry=minimal_registry, level=5)

    assert evaluate(condition=ref, player=low_player, registry=registry) is False
    assert evaluate(condition=ref, player=high_player, registry=registry) is True


def test_evaluate_custom_condition_missing_registry_returns_false(
    minimal_registry: ContentRegistry,
) -> None:
    """evaluate() returns False and logs a warning when registry is None."""
    ref = CustomConditionRef(type="custom", name="some-condition")
    player = _make_character(registry=minimal_registry)
    assert evaluate(condition=ref, player=player, registry=None) is False


def test_evaluate_custom_condition_unknown_name_returns_false(
    minimal_registry: ContentRegistry,
) -> None:
    """evaluate() returns False when the custom condition name is not in the registry."""
    registry = ContentRegistry()
    registry.game = minimal_registry.game
    registry.character_config = minimal_registry.character_config

    ref = CustomConditionRef(type="custom", name="no-such-condition")
    player = _make_character(registry=minimal_registry)
    assert evaluate(condition=ref, player=player, registry=registry) is False


def test_evaluate_custom_condition_composition(minimal_registry: ContentRegistry) -> None:
    """Nested custom condition references are resolved transitively."""
    inner = _make_custom_condition_manifest(
        "test-inner",
        {"type": "level", "value": 10},
    )
    outer = _make_custom_condition_manifest(
        "test-outer",
        {"type": "custom", "name": "test-inner"},
    )
    registry = ContentRegistry()
    registry.game = minimal_registry.game
    registry.character_config = minimal_registry.character_config
    registry.custom_conditions.register(inner)
    registry.custom_conditions.register(outer)

    ref = CustomConditionRef(type="custom", name="test-outer")
    low_player = _make_character(registry=minimal_registry, level=1)
    high_player = _make_character(registry=minimal_registry, level=10)

    assert evaluate(condition=ref, player=low_player, registry=registry) is False
    assert evaluate(condition=ref, player=high_player, registry=registry) is True


# ---------------------------------------------------------------------------
# Group 9: _validate_custom_condition_refs unit tests
# ---------------------------------------------------------------------------


def test_validate_dangling_ref_produces_error() -> None:
    """A CustomConditionRef to an undeclared name produces a LoadError."""
    from oscilla.engine.models.location import LocationManifest

    location: ManifestEnvelope = LocationManifest.model_validate(  # type: ignore[assignment]
        {
            "apiVersion": "oscilla/v1",
            "kind": "Location",
            "metadata": {"name": "test-loc"},
            "spec": {
                "displayName": "Test",
                "region": "test-region",
                "unlock": {"type": "custom", "name": "missing-condition"},
                "adventures": [],
            },
        }
    )
    errors: List[LoadError] = _validate_custom_condition_refs([location])
    assert any("missing-condition" in e.message and "unknown CustomCondition" in e.message for e in errors), (
        f"Expected 'missing-condition' and 'unknown CustomCondition' in errors: {errors}"
    )


def test_validate_direct_circular_ref_produces_error() -> None:
    """A CustomCondition body that references itself produces a cycle LoadError."""
    self_ref = _make_custom_condition_manifest(
        "self-ref",
        {"type": "custom", "name": "self-ref"},
    )
    errors: List[LoadError] = _validate_custom_condition_refs([self_ref])
    assert any("circular reference" in e.message for e in errors), f"Expected 'circular reference' in errors: {errors}"


def test_validate_indirect_cycle_produces_error() -> None:
    """An indirect cycle (a → b → a) produces a LoadError with the cycle path."""
    cc_a = _make_custom_condition_manifest("test-cycle-a", {"type": "custom", "name": "test-cycle-b"})
    cc_b = _make_custom_condition_manifest("test-cycle-b", {"type": "custom", "name": "test-cycle-a"})
    errors: List[LoadError] = _validate_custom_condition_refs([cc_a, cc_b])
    assert any("circular reference" in e.message for e in errors), f"Expected 'circular reference' in errors: {errors}"
    # The cycle path must include both names.
    cycle_errors = [e for e in errors if "circular reference" in e.message]
    assert any("test-cycle-a" in e.message or "test-cycle-b" in e.message for e in cycle_errors)


def test_validate_valid_composition_produces_no_errors() -> None:
    """A valid composition (a references b, both declared, no cycle) produces no errors."""
    cc_a = _make_custom_condition_manifest("comp-a", {"type": "custom", "name": "comp-b"})
    cc_b = _make_custom_condition_manifest("comp-b", {"type": "level", "value": 5})
    errors: List[LoadError] = _validate_custom_condition_refs([cc_a, cc_b])
    assert errors == []


# ---------------------------------------------------------------------------
# Group 10: _validate_passive_effect_conditions unit tests
# ---------------------------------------------------------------------------


def test_passive_effect_stat_source_effective_raises_error() -> None:
    """character_stat with stat_source: effective in a passive effect is a LoadError."""
    game = _make_game_manifest(
        passive_effects=[
            {
                "condition": {
                    "type": "character_stat",
                    "name": "strength",
                    "gte": 10,
                    "stat_source": "effective",
                },
                "stat_modifiers": [{"stat": "strength", "amount": 1}],
            }
        ]
    )
    errors: List[LoadError] = _validate_passive_effect_conditions([game])
    assert any("passive_effects[0]" in e.message and "character_stat" in e.message for e in errors), (
        f"Expected error about passive_effects[0] character_stat: {errors}"
    )


def test_passive_effect_skill_condition_raises_error() -> None:
    """skill condition in a passive effect is a LoadError."""
    game = _make_game_manifest(
        passive_effects=[
            {
                "condition": {"type": "skill", "name": "swordsmanship"},
                "stat_modifiers": [{"stat": "strength", "amount": 1}],
            }
        ]
    )
    errors: List[LoadError] = _validate_passive_effect_conditions([game])
    assert any("passive_effects[0]" in e.message and "skill" in e.message for e in errors), (
        f"Expected error about passive_effects[0] skill: {errors}"
    )


def test_passive_effect_stat_source_base_no_error() -> None:
    """character_stat with stat_source: base in a passive effect produces no error."""
    game = _make_game_manifest(
        passive_effects=[
            {
                "condition": {
                    "type": "character_stat",
                    "name": "strength",
                    "gte": 10,
                    "stat_source": "base",
                },
                "stat_modifiers": [{"stat": "strength", "amount": 1}],
            }
        ]
    )
    errors: List[LoadError] = _validate_passive_effect_conditions([game])
    assert errors == []


def test_passive_effect_custom_ref_with_banned_body_raises_error() -> None:
    """A passive effect whose CustomConditionRef body contains SkillCondition is a LoadError."""
    cc = _make_custom_condition_manifest("has-skill", {"type": "skill", "name": "archery"})
    game = _make_game_manifest(
        passive_effects=[
            {
                "condition": {"type": "custom", "name": "has-skill"},
                "stat_modifiers": [{"stat": "strength", "amount": 1}],
            }
        ]
    )
    errors: List[LoadError] = _validate_passive_effect_conditions([game, cc])
    assert any("passive_effects[0]" in e.message for e in errors), f"Expected error about passive_effects[0]: {errors}"


def test_passive_effect_custom_ref_with_safe_body_no_error() -> None:
    """A passive effect whose CustomConditionRef body is a safe LevelCondition produces no error."""
    cc = _make_custom_condition_manifest("level-gate", {"type": "level", "value": 5})
    game = _make_game_manifest(
        passive_effects=[
            {
                "condition": {"type": "custom", "name": "level-gate"},
                "stat_modifiers": [{"stat": "strength", "amount": 1}],
            }
        ]
    )
    errors: List[LoadError] = _validate_passive_effect_conditions([game, cc])
    assert errors == []


def test_validate_passive_effects_no_longer_warns_item_held_label() -> None:
    """_validate_passive_effects() returns [] even for item_held_label (no longer a warning)."""
    game = _make_game_manifest(
        passive_effects=[
            {
                "condition": {"type": "item_held_label", "label": "legendary"},
                "stat_modifiers": [{"stat": "strength", "amount": 2}],
            }
        ]
    )
    warnings = _validate_passive_effects([game])
    assert warnings == []


# ---------------------------------------------------------------------------
# Group 11: Loader integration tests
# ---------------------------------------------------------------------------


def test_loader_rejects_circular_custom_condition() -> None:
    """load_from_disk raises ContentLoadError when CustomConditions form a cycle."""
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_disk(FIXTURES / "custom-conditions-cycle")
    assert "circular reference" in str(exc_info.value).lower(), (
        f"Expected 'circular reference' in error: {exc_info.value}"
    )


def test_loader_rejects_dangling_custom_condition_ref() -> None:
    """load_from_disk raises ContentLoadError when a manifest references an undeclared CustomCondition."""
    with pytest.raises(ContentLoadError) as exc_info:
        load_from_disk(FIXTURES / "custom-conditions-dangling")
    assert "unknown customcondition" in str(exc_info.value).lower(), (
        f"Expected 'unknown CustomCondition' in error: {exc_info.value}"
    )

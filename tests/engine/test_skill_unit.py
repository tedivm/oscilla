"""Unit tests for the skill and buff model layer, CharacterState skill methods,
and the pure arithmethic helpers in combat.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

import pytest

from oscilla.engine.character import CharacterState

if TYPE_CHECKING:
    from oscilla.engine.registry import ContentRegistry

from oscilla.engine.combat_context import ActiveCombatEffect, CombatContext
from oscilla.engine.models.base import SkillCondition
from oscilla.engine.models.buff import (
    BuffSpec,
    DamageAmplifyModifier,
    DamageReductionModifier,
    DamageReflectModifier,
    DamageVulnerabilityModifier,
)
from oscilla.engine.models.skill import SkillCooldown
from oscilla.engine.steps.combat import _apply_damage_amplify, _apply_incoming_modifiers

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_ctx() -> CombatContext:
    return CombatContext(enemy_hp=100, enemy_ref="test-enemy")


def _ctx_with_effects(effects: List[ActiveCombatEffect]) -> CombatContext:
    ctx = _empty_ctx()
    ctx.active_effects = list(effects)
    return ctx


def _amplify_effect(target: str, percent: int) -> ActiveCombatEffect:
    return ActiveCombatEffect(
        source_skill="test-skill",
        target=target,  # type: ignore[arg-type]
        remaining_turns=3,
        per_turn_effects=[],
        modifiers=[DamageAmplifyModifier(type="damage_amplify", target=target, percent=percent)],
    )


def _reduction_effect(target: str, percent: int) -> ActiveCombatEffect:
    return ActiveCombatEffect(
        source_skill="test-skill",
        target=target,  # type: ignore[arg-type]
        remaining_turns=3,
        per_turn_effects=[],
        modifiers=[DamageReductionModifier(type="damage_reduction", target=target, percent=percent)],
    )


def _vulnerability_effect(target: str, percent: int) -> ActiveCombatEffect:
    return ActiveCombatEffect(
        source_skill="test-skill",
        target=target,  # type: ignore[arg-type]
        remaining_turns=3,
        per_turn_effects=[],
        modifiers=[DamageVulnerabilityModifier(type="damage_vulnerability", target=target, percent=percent)],
    )


def _reflect_effect(target: str, percent: int) -> ActiveCombatEffect:
    return ActiveCombatEffect(
        source_skill="test-skill",
        target=target,  # type: ignore[arg-type]
        remaining_turns=3,
        per_turn_effects=[],
        modifiers=[DamageReflectModifier(type="damage_reflect", target=target, percent=percent)],
    )


# ---------------------------------------------------------------------------
# BuffSpec validator tests (11.1a)
# ---------------------------------------------------------------------------


def test_buffspec_rejects_empty_modifiers_and_effects() -> None:
    with pytest.raises(Exception, match="at least one"):
        BuffSpec(displayName="Empty", duration_turns=2, per_turn_effects=[], modifiers=[])


def test_buffspec_accepts_modifier_only() -> None:
    spec = BuffSpec(
        displayName="Shield",
        duration_turns=3,
        modifiers=[DamageReductionModifier(type="damage_reduction", target="player", percent=50)],
    )
    assert len(spec.modifiers) == 1
    assert spec.per_turn_effects == []


def test_buffspec_accepts_tick_only() -> None:
    from oscilla.engine.models.adventure import StatChangeEffect

    spec = BuffSpec(
        displayName="Poison",
        duration_turns=3,
        per_turn_effects=[StatChangeEffect(type="stat_change", stat="hp", amount=-3)],
    )
    assert len(spec.per_turn_effects) == 1
    assert spec.modifiers == []


def test_buffspec_accepts_combined_tick_and_modifier() -> None:
    from oscilla.engine.models.adventure import StatChangeEffect

    spec = BuffSpec(
        displayName="BurningShield",
        duration_turns=3,
        per_turn_effects=[StatChangeEffect(type="stat_change", stat="hp", amount=-1)],
        modifiers=[DamageReductionModifier(type="damage_reduction", target="player", percent=25)],
    )
    assert len(spec.per_turn_effects) == 1
    assert len(spec.modifiers) == 1


# ---------------------------------------------------------------------------
# CombatModifier discriminated union tests (11.1b)
# ---------------------------------------------------------------------------


def test_damage_reduction_modifier() -> None:
    mod = DamageReductionModifier(type="damage_reduction", target="player", percent=30)
    assert mod.type == "damage_reduction"
    assert mod.percent == 30
    assert mod.target == "player"


def test_damage_amplify_modifier() -> None:
    mod = DamageAmplifyModifier(type="damage_amplify", target="player", percent=50)
    assert mod.type == "damage_amplify"
    assert mod.percent == 50


def test_damage_reflect_modifier() -> None:
    mod = DamageReflectModifier(type="damage_reflect", target="player", percent=25)
    assert mod.type == "damage_reflect"
    assert mod.percent == 25


def test_damage_vulnerability_modifier() -> None:
    mod = DamageVulnerabilityModifier(type="damage_vulnerability", target="player", percent=20)
    assert mod.type == "damage_vulnerability"
    assert mod.percent == 20


# ---------------------------------------------------------------------------
# _apply_damage_amplify tests (11.1c)
# ---------------------------------------------------------------------------


def test_amplify_no_active_effects() -> None:
    ctx = _empty_ctx()
    assert _apply_damage_amplify(10, "player", ctx) == 10


def test_amplify_single_modifier() -> None:
    ctx = _ctx_with_effects([_amplify_effect("player", 50)])
    # 10 * (1 + 50/100) = 15
    assert _apply_damage_amplify(10, "player", ctx) == 15


def test_amplify_stacked_modifiers() -> None:
    ctx = _ctx_with_effects(
        [
            _amplify_effect("player", 50),
            _amplify_effect("player", 50),
        ]
    )
    # 10 * (1 + 100/100) = 20
    assert _apply_damage_amplify(10, "player", ctx) == 20


def test_amplify_wrong_target_ignored() -> None:
    # Amplifier is for "enemy", checking "player" — should have no effect.
    ctx = _ctx_with_effects([_amplify_effect("enemy", 50)])
    assert _apply_damage_amplify(10, "player", ctx) == 10


def test_amplify_zero_base_damage() -> None:
    ctx = _ctx_with_effects([_amplify_effect("player", 100)])
    assert _apply_damage_amplify(0, "player", ctx) == 0


# ---------------------------------------------------------------------------
# _apply_incoming_modifiers tests (11.1c)
# ---------------------------------------------------------------------------


def test_incoming_no_active_effects() -> None:
    ctx = _empty_ctx()
    assert _apply_incoming_modifiers(10, "player", ctx) == 10


def test_incoming_reduction_modifier() -> None:
    ctx = _ctx_with_effects([_reduction_effect("player", 50)])
    # 10 * (1 - 0.5) = 5
    assert _apply_incoming_modifiers(10, "player", ctx) == 5


def test_incoming_stacked_reductions() -> None:
    ctx = _ctx_with_effects(
        [
            _reduction_effect("player", 30),
            _reduction_effect("player", 20),
        ]
    )
    # 10 * (1 - 0.5) = 5
    assert _apply_incoming_modifiers(10, "player", ctx) == 5


def test_incoming_reduction_capped_at_minimum_1() -> None:
    # Even 99% reduction produces at least 1 when base > 0.
    ctx = _ctx_with_effects([_reduction_effect("player", 99)])
    assert _apply_incoming_modifiers(1, "player", ctx) == 1


def test_incoming_vulnerability_modifier() -> None:
    ctx = _ctx_with_effects([_vulnerability_effect("player", 50)])
    # 10 * (1 + 0.5) = 15
    assert _apply_incoming_modifiers(10, "player", ctx) == 15


def test_incoming_reduction_and_vulnerability_combined() -> None:
    # 50% reduction + 20% vulnerability: factor = 1 - 0.5 + 0.2 = 0.7 → 7
    ctx = _ctx_with_effects(
        [
            _reduction_effect("player", 50),
            _vulnerability_effect("player", 20),
        ]
    )
    assert _apply_incoming_modifiers(10, "player", ctx) == 7


def test_incoming_zero_base_damage() -> None:
    ctx = _ctx_with_effects([_reduction_effect("player", 50)])
    assert _apply_incoming_modifiers(0, "player", ctx) == 0


def test_incoming_wrong_target_ignored() -> None:
    # Reduction is for "enemy"; checking "player" should not apply it.
    ctx = _ctx_with_effects([_reduction_effect("enemy", 50)])
    assert _apply_incoming_modifiers(10, "player", ctx) == 10


def test_incoming_enemy_target() -> None:
    """Modifier targeting enemy is applied on the enemy path."""
    ctx = _ctx_with_effects([_reduction_effect("enemy", 50)])
    assert _apply_incoming_modifiers(10, "enemy", ctx) == 5


# ---------------------------------------------------------------------------
# BuffSpec.variables and variable ref tests (11.1d)
# ---------------------------------------------------------------------------


def test_buffspec_int_percent_resolves_directly() -> None:
    spec = BuffSpec(
        displayName="Shield",
        duration_turns=3,
        modifiers=[DamageReductionModifier(type="damage_reduction", target="player", percent=50)],
    )
    mod = spec.modifiers[0]
    assert isinstance(mod.percent, int)
    assert mod.percent == 50


def test_buffspec_variable_name_resolves_from_variables() -> None:
    spec = BuffSpec(
        displayName="Rage",
        duration_turns=2,
        variables={"rage_percent": 40},
        modifiers=[DamageAmplifyModifier(type="damage_amplify", target="player", percent="rage_percent")],
    )
    mod = spec.modifiers[0]
    assert isinstance(mod.percent, str)
    assert mod.percent == "rage_percent"
    assert spec.variables["rage_percent"] == 40


def test_buffspec_undeclared_variable_raises_error() -> None:
    with pytest.raises(Exception, match="not declared in variables"):
        BuffSpec(
            displayName="Bad Buff",
            duration_turns=2,
            variables={},  # empty — rage_percent is not declared
            modifiers=[DamageAmplifyModifier(type="damage_amplify", target="player", percent="rage_percent")],
        )


# ---------------------------------------------------------------------------
# CombatModifier field validator tests (11.1e)
# ---------------------------------------------------------------------------


def test_damage_reduction_percent_str_passes() -> None:
    mod = DamageReductionModifier(type="damage_reduction", target="player", percent="some_variable")
    assert mod.percent == "some_variable"


def test_damage_reduction_percent_int_in_range_passes() -> None:
    mod = DamageReductionModifier(type="damage_reduction", target="player", percent=50)
    assert mod.percent == 50


def test_damage_reduction_percent_zero_raises() -> None:
    with pytest.raises(Exception, match="1.99"):
        DamageReductionModifier(type="damage_reduction", target="player", percent=0)


def test_damage_reduction_percent_100_raises() -> None:
    with pytest.raises(Exception, match="1.99"):
        DamageReductionModifier(type="damage_reduction", target="player", percent=100)


def test_damage_amplify_percent_zero_raises() -> None:
    with pytest.raises(Exception):
        DamageAmplifyModifier(type="damage_amplify", target="player", percent=0)


def test_damage_amplify_percent_positive_passes() -> None:
    mod = DamageAmplifyModifier(type="damage_amplify", target="player", percent=1)
    assert mod.percent == 1


def test_damage_reflect_percent_100_passes() -> None:
    mod = DamageReflectModifier(type="damage_reflect", target="player", percent=100)
    assert mod.percent == 100


def test_damage_reflect_percent_zero_raises() -> None:
    with pytest.raises(Exception):
        DamageReflectModifier(type="damage_reflect", target="player", percent=0)


# ---------------------------------------------------------------------------
# SkillCondition tests (11.2)
# ---------------------------------------------------------------------------


def test_skill_condition_default_mode_is_available() -> None:
    cond = SkillCondition(type="skill", name="test-skill-fireball")
    assert cond.mode == "available"


def test_skill_condition_learned_mode() -> None:
    cond = SkillCondition(type="skill", name="test-skill-fireball", mode="learned")
    assert cond.mode == "learned"


def test_skill_condition_invalid_mode_raises() -> None:
    with pytest.raises(Exception):
        SkillCondition(type="skill", name="test-skill", mode="unknown_mode")


# ---------------------------------------------------------------------------
# SkillCooldown model tests
# ---------------------------------------------------------------------------


def test_skill_cooldown_turn_scope() -> None:
    cooldown = SkillCooldown(scope="turn", count=2)
    assert cooldown.scope == "turn"
    assert cooldown.count == 2


def test_skill_cooldown_adventure_scope() -> None:
    cooldown = SkillCooldown(scope="adventure", count=1)
    assert cooldown.scope == "adventure"


def test_skill_cooldown_count_zero_raises() -> None:
    with pytest.raises(Exception):
        SkillCooldown(scope="turn", count=0)


# ---------------------------------------------------------------------------
# CharacterState.grant_skill() tests (11.3)
# ---------------------------------------------------------------------------


def test_grant_skill_new_skill(base_player: CharacterState) -> None:
    result = base_player.grant_skill("some-skill-ref")
    assert result is True
    assert "some-skill-ref" in base_player.known_skills


def test_grant_skill_duplicate_returns_false(base_player: CharacterState) -> None:
    base_player.grant_skill("dup-skill")
    result = base_player.grant_skill("dup-skill")
    assert result is False
    assert (
        base_player.known_skills.count("dup-skill")
        if hasattr(base_player.known_skills, "count")
        else sum(1 for s in base_player.known_skills if s == "dup-skill") == 1
    )


def test_grant_skill_without_registry(base_player: CharacterState) -> None:
    """Without a registry, grant_skill always succeeds (no category rules to enforce)."""
    result = base_player.grant_skill("anything", registry=None)
    assert result is True
    assert "anything" in base_player.known_skills


# ---------------------------------------------------------------------------
# CharacterState.available_skills() tests (11.4)
# ---------------------------------------------------------------------------


def test_available_skills_no_registry(base_player: CharacterState) -> None:
    base_player.known_skills.add("learned-skill")
    skills = base_player.available_skills(registry=None)
    assert "learned-skill" in skills


def test_available_skills_includes_known(base_player: CharacterState) -> None:
    base_player.known_skills = {"s1", "s2"}
    skills = base_player.available_skills()
    assert "s1" in skills
    assert "s2" in skills


# ---------------------------------------------------------------------------
# CharacterState.tick_skill_cooldowns() tests (11.5)
# ---------------------------------------------------------------------------


def test_tick_skill_cooldowns_decrements(base_player: CharacterState) -> None:
    base_player.skill_cooldowns = {"fireball": 3}
    base_player.tick_skill_cooldowns()
    assert base_player.skill_cooldowns["fireball"] == 2


def test_tick_skill_cooldowns_removes_on_zero(base_player: CharacterState) -> None:
    base_player.skill_cooldowns = {"fireball": 1}
    base_player.tick_skill_cooldowns()
    assert "fireball" not in base_player.skill_cooldowns


def test_tick_skill_cooldowns_multiple_skills(base_player: CharacterState) -> None:
    base_player.skill_cooldowns = {"a": 1, "b": 2, "c": 3}
    base_player.tick_skill_cooldowns()
    assert "a" not in base_player.skill_cooldowns
    assert base_player.skill_cooldowns["b"] == 1
    assert base_player.skill_cooldowns["c"] == 2


def test_tick_skill_cooldowns_empty_dict(base_player: CharacterState) -> None:
    base_player.skill_cooldowns = {}
    base_player.tick_skill_cooldowns()
    assert base_player.skill_cooldowns == {}


# ---------------------------------------------------------------------------
# CharacterState serialization roundtrip tests (11.6)
# ---------------------------------------------------------------------------


def test_known_skills_roundtrip(base_player: CharacterState, minimal_registry: "ContentRegistry") -> None:
    base_player.known_skills = {"skill-a", "skill-b"}
    data = base_player.to_dict()
    assert minimal_registry.character_config is not None
    restored = CharacterState.from_dict(data, character_config=minimal_registry.character_config)
    assert restored.known_skills == {"skill-a", "skill-b"}


def test_skill_cooldowns_roundtrip(base_player: CharacterState, minimal_registry: "ContentRegistry") -> None:
    base_player.skill_cooldowns = {"skill-a": 2, "skill-b": 5}
    data = base_player.to_dict()
    assert minimal_registry.character_config is not None
    restored = CharacterState.from_dict(data, character_config=minimal_registry.character_config)
    assert restored.skill_cooldowns == {"skill-a": 2, "skill-b": 5}


def test_empty_skills_roundtrip(base_player: CharacterState, minimal_registry: "ContentRegistry") -> None:
    base_player.known_skills = set()
    base_player.skill_cooldowns = {}
    data = base_player.to_dict()
    assert minimal_registry.character_config is not None
    restored = CharacterState.from_dict(data, character_config=minimal_registry.character_config)
    assert restored.known_skills == set()
    assert restored.skill_cooldowns == {}


# ---------------------------------------------------------------------------
# CombatContext initialization tests (3.2)
# ---------------------------------------------------------------------------


def test_combat_context_default_resources_empty() -> None:
    """CombatContext initializes with empty enemy_resources when none are supplied."""
    ctx = CombatContext(enemy_hp=50, enemy_ref="test-enemy")
    assert ctx.enemy_resources == {}


def test_combat_context_resources_populated_from_spec() -> None:
    """enemy_resources is populated from the value passed in (mirrors EnemySpec.skill_resources)."""
    ctx = CombatContext(enemy_hp=50, enemy_ref="fire-mage", enemy_resources={"mana": 80})
    assert ctx.enemy_resources["mana"] == 80


def test_combat_context_resources_supports_multiple_keys() -> None:
    """Multiple resource pools can be tracked simultaneously."""
    resources = {"mana": 80, "rage": 40}
    ctx = CombatContext(enemy_hp=100, enemy_ref="dual-resource-enemy", enemy_resources=dict(resources))
    assert ctx.enemy_resources == {"mana": 80, "rage": 40}


def test_combat_context_resource_mutation_does_not_affect_original() -> None:
    """Mutating enemy_resources does not affect the original dict (dict() copy)."""
    original: dict[str, int] = {"mana": 80}
    ctx = CombatContext(enemy_hp=50, enemy_ref="test", enemy_resources=dict(original))
    ctx.enemy_resources["mana"] = 0
    assert original["mana"] == 80


def test_combat_context_initial_turn_number() -> None:
    """CombatContext starts at turn 1."""
    ctx = CombatContext(enemy_hp=50, enemy_ref="test-enemy")
    assert ctx.turn_number == 1


def test_combat_context_initial_active_effects_empty() -> None:
    """CombatContext starts with no active effects."""
    ctx = CombatContext(enemy_hp=50, enemy_ref="test-enemy")
    assert ctx.active_effects == []


def test_combat_context_initial_skill_uses_empty() -> None:
    """CombatContext starts with no recorded skill uses."""
    ctx = CombatContext(enemy_hp=50, enemy_ref="test-enemy")
    assert ctx.skill_uses_this_combat == {}

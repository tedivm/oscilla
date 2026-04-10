"""Tests for ArchetypeAddEffect, ArchetypeRemoveEffect, SkillRevokeEffect, and archetype passive effects."""

from __future__ import annotations

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import (
    ArchetypeAddEffect,
    ArchetypeRemoveEffect,
    SkillRevokeEffect,
    StatChangeEffect,
)
from oscilla.engine.models.archetype import ArchetypeManifest, ArchetypeSpec
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.character_config import CharacterConfigManifest, CharacterConfigSpec, StatDefinition
from oscilla.engine.models.game import GameManifest, GameSpec, PassiveEffect
from oscilla.engine.models.item import StatModifier
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.effects import run_effect
from tests.engine.conftest import MockTUI

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry(
    *archetype_specs: tuple[str, ArchetypeSpec],
) -> ContentRegistry:
    """Build a minimal registry with the given archetypes registered."""
    registry = ContentRegistry()

    game = GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(displayName="Test Game"),
    )
    registry.game = game

    char_config = CharacterConfigManifest(
        apiVersion="oscilla/v1",
        kind="CharacterConfig",
        metadata=Metadata(name="test-char"),
        spec=CharacterConfigSpec(
            public_stats=[
                StatDefinition(name="strength", type="int", default=10),
            ],
            hidden_stats=[],
        ),
    )
    registry.character_config = char_config

    for name, spec in archetype_specs:
        manifest = ArchetypeManifest(
            apiVersion="oscilla/v1",
            kind="Archetype",
            metadata=Metadata(name=name),
            spec=spec,
        )
        registry.archetypes.register(manifest)

    return registry


def _make_player(registry: ContentRegistry) -> CharacterState:
    game = registry.game
    char_config = registry.character_config
    assert game is not None
    assert char_config is not None
    return CharacterState.new_character(
        name="Test Player",
        game_manifest=game,
        character_config=char_config,
    )


# ---------------------------------------------------------------------------
# ArchetypeAddEffect (tasks 8.7-8.8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archetype_add_grants_archetype() -> None:
    """ArchetypeAddEffect adds the named archetype to player.archetypes."""
    registry = _make_registry(("warrior", ArchetypeSpec(displayName="Warrior")))
    player = _make_player(registry)

    effect = ArchetypeAddEffect(type="archetype_add", name="warrior")
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())

    assert "warrior" in player.archetypes


@pytest.mark.asyncio
async def test_archetype_add_fires_gain_effects() -> None:
    """ArchetypeAddEffect dispatches the archetype's gain_effects once."""
    gain = StatChangeEffect(type="stat_change", stat="strength", amount=5)
    spec = ArchetypeSpec(displayName="Warrior", gain_effects=[gain])
    registry = _make_registry(("warrior", spec))
    player = _make_player(registry)
    original_strength = player.stats["strength"]

    effect = ArchetypeAddEffect(type="archetype_add", name="warrior")
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())

    assert player.stats["strength"] == original_strength + 5


@pytest.mark.asyncio
async def test_archetype_add_is_noop_if_already_held() -> None:
    """Adding an already-held archetype without force is a no-op (gain_effects do not re-fire)."""
    gain = StatChangeEffect(type="stat_change", stat="strength", amount=5)
    spec = ArchetypeSpec(displayName="Warrior", gain_effects=[gain])
    registry = _make_registry(("warrior", spec))
    player = _make_player(registry)

    # First grant
    effect = ArchetypeAddEffect(type="archetype_add", name="warrior")
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())
    strength_after_first = player.stats["strength"]

    # Second grant — should be a no-op
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())
    assert player.stats["strength"] == strength_after_first


@pytest.mark.asyncio
async def test_archetype_add_force_regrants_and_refires_gain_effects() -> None:
    """force=True re-adds the archetype and re-fires gain_effects even if already held."""
    gain = StatChangeEffect(type="stat_change", stat="strength", amount=5)
    spec = ArchetypeSpec(displayName="Warrior", gain_effects=[gain])
    registry = _make_registry(("warrior", spec))
    player = _make_player(registry)
    original_strength = player.stats["strength"]

    effect = ArchetypeAddEffect(type="archetype_add", name="warrior", force=True)
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())

    # gain_effects should have fired twice
    assert player.stats["strength"] == original_strength + 10


# ---------------------------------------------------------------------------
# ArchetypeRemoveEffect (task 8.9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archetype_remove_removes_archetype() -> None:
    """ArchetypeRemoveEffect removes the named archetype from player.archetypes."""
    registry = _make_registry(("warrior", ArchetypeSpec(displayName="Warrior")))
    player = _make_player(registry)
    player.archetypes["warrior"] = player.make_grant_record()

    effect = ArchetypeRemoveEffect(type="archetype_remove", name="warrior")
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())

    assert "warrior" not in player.archetypes


@pytest.mark.asyncio
async def test_archetype_remove_fires_lose_effects() -> None:
    """ArchetypeRemoveEffect dispatches the archetype's lose_effects once."""
    lose = StatChangeEffect(type="stat_change", stat="strength", amount=-5)
    spec = ArchetypeSpec(displayName="Warrior", lose_effects=[lose])
    registry = _make_registry(("warrior", spec))
    player = _make_player(registry)
    player.archetypes["warrior"] = player.make_grant_record()
    original_strength = player.stats["strength"]

    effect = ArchetypeRemoveEffect(type="archetype_remove", name="warrior")
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())

    assert player.stats["strength"] == original_strength - 5


@pytest.mark.asyncio
async def test_archetype_remove_noop_when_not_held() -> None:
    """Removing an archetype not held without force is a no-op."""
    lose = StatChangeEffect(type="stat_change", stat="strength", amount=-5)
    spec = ArchetypeSpec(displayName="Warrior", lose_effects=[lose])
    registry = _make_registry(("warrior", spec))
    player = _make_player(registry)
    original_strength = player.stats["strength"]

    effect = ArchetypeRemoveEffect(type="archetype_remove", name="warrior")
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())

    # lose_effects must NOT have fired
    assert player.stats["strength"] == original_strength
    assert "warrior" not in player.archetypes


@pytest.mark.asyncio
async def test_archetype_remove_force_fires_lose_effects_even_when_not_held() -> None:
    """force=True fires lose_effects even when the archetype was not held."""
    lose = StatChangeEffect(type="stat_change", stat="strength", amount=-5)
    spec = ArchetypeSpec(displayName="Warrior", lose_effects=[lose])
    registry = _make_registry(("warrior", spec))
    player = _make_player(registry)
    original_strength = player.stats["strength"]

    effect = ArchetypeRemoveEffect(type="archetype_remove", name="warrior", force=True)
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())

    assert player.stats["strength"] == original_strength - 5


# ---------------------------------------------------------------------------
# SkillRevokeEffect (task 8.9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_revoke_removes_known_skill() -> None:
    """SkillRevokeEffect removes the skill from player.known_skills."""
    registry = _make_registry()
    player = _make_player(registry)
    player.known_skills.add("fireball")

    effect = SkillRevokeEffect(type="skill_revoke", skill="fireball")
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())

    assert "fireball" not in player.known_skills


@pytest.mark.asyncio
async def test_skill_revoke_noop_when_not_known() -> None:
    """SkillRevokeEffect is a no-op when the skill was not known."""
    registry = _make_registry()
    player = _make_player(registry)

    effect = SkillRevokeEffect(type="skill_revoke", skill="fireball")
    # Must not raise
    await run_effect(effect=effect, player=player, registry=registry, tui=MockTUI())

    assert "fireball" not in player.known_skills


# ---------------------------------------------------------------------------
# Archetype passive effects (tasks 8.10-8.11)
# ---------------------------------------------------------------------------


def test_archetype_passive_stat_grant_applied_in_effective_stats() -> None:
    """effective_stats() includes stat bonuses from held archetype passive_effects."""
    passive = PassiveEffect(
        stat_modifiers=[StatModifier(stat="strength", amount=7)],
    )
    spec = ArchetypeSpec(displayName="Warrior", passive_effects=[passive])
    registry = _make_registry(("warrior", spec))
    player = _make_player(registry)
    base_strength = player.effective_stats(registry=registry)["strength"]

    player.archetypes["warrior"] = player.make_grant_record()
    boosted_strength = player.effective_stats(registry=registry)["strength"]

    assert boosted_strength == base_strength + 7


def test_archetype_not_held_passive_not_applied() -> None:
    """passive_effects do not apply when the archetype is not held."""
    passive = PassiveEffect(
        stat_modifiers=[StatModifier(stat="strength", amount=7)],
    )
    spec = ArchetypeSpec(displayName="Warrior", passive_effects=[passive])
    registry = _make_registry(("warrior", spec))
    player = _make_player(registry)

    stats = player.effective_stats(registry=registry)
    assert stats["strength"] == 10  # base only


def test_archetype_passive_skill_grant_applied_in_available_skills() -> None:
    """available_skills() includes skills granted by held archetype passive_effects."""
    passive = PassiveEffect(
        skill_grants=["fireball"],
    )
    spec = ArchetypeSpec(displayName="Mage", passive_effects=[passive])
    registry = _make_registry(("mage", spec))
    player = _make_player(registry)

    assert "fireball" not in player.available_skills(registry=registry)

    player.archetypes["mage"] = player.make_grant_record()
    assert "fireball" in player.available_skills(registry=registry)


# ---------------------------------------------------------------------------
# End-to-end: archetype_remove -> lose_effects -> skill_revoke chain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archetype_remove_lose_effects_revokes_skill() -> None:
    """Removing an archetype whose lose_effects contains skill_revoke removes the skill.

    Covers the spec scenario: skill_revoke in archetype lose_effects fires on archetype removal.
    The archetype is granted first (adding the skill to known_skills via gain_effects), then
    removed, verifying the skill disappears via the lose_effects chain.
    """
    from oscilla.engine.models.adventure import SkillGrantEffect

    gain = SkillGrantEffect(type="skill_grant", skill="power-attack")
    lose = SkillRevokeEffect(type="skill_revoke", skill="power-attack")
    spec = ArchetypeSpec(displayName="Warrior", gain_effects=[gain], lose_effects=[lose])
    registry = _make_registry(("warrior", spec))
    player = _make_player(registry)

    # Grant the archetype — gain_effects fire, skill is learned
    add_effect = ArchetypeAddEffect(type="archetype_add", name="warrior")
    await run_effect(effect=add_effect, player=player, registry=registry, tui=MockTUI())
    assert "power-attack" in player.known_skills
    assert "warrior" in player.archetypes

    # Remove the archetype — lose_effects fire, skill_revoke removes the skill
    remove_effect = ArchetypeRemoveEffect(type="archetype_remove", name="warrior")
    await run_effect(effect=remove_effect, player=player, registry=registry, tui=MockTUI())
    assert "warrior" not in player.archetypes
    assert "power-attack" not in player.known_skills

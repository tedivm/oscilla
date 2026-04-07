"""Tests for the PrestigeEffect handler."""

from __future__ import annotations

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import PrestigeEffect, StatChangeEffect
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.character_config import CharacterConfigManifest, CharacterConfigSpec, StatDefinition
from oscilla.engine.models.game import GameManifest, GameSpec, HpFormula, PrestigeConfig
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.steps.effects import run_effect
from tests.engine.conftest import MockTUI


def _build_prestige_registry(
    *,
    carry_stats: list[str] | None = None,
    carry_skills: list[str] | None = None,
    pre_prestige_effects: list | None = None,
    post_prestige_effects: list | None = None,
) -> ContentRegistry:
    """Return a registry wired with prestige config and legacy_power hidden stat."""
    registry = ContentRegistry()

    registry.game = GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-prestige-game"),
        spec=GameSpec(
            displayName="Prestige Test Game",
            xp_thresholds=[100, 200, 300],
            hp_formula=HpFormula(base_hp=20, hp_per_level=5),
            prestige=PrestigeConfig(
                carry_stats=carry_stats or ["legacy_power"],
                carry_skills=carry_skills or [],
                pre_prestige_effects=pre_prestige_effects
                or [StatChangeEffect(type="stat_change", stat="legacy_power", amount=1)],
                post_prestige_effects=post_prestige_effects or [],
            ),
        ),
    )

    registry.character_config = CharacterConfigManifest(
        apiVersion="oscilla/v1",
        kind="CharacterConfig",
        metadata=Metadata(name="test-prestige-char-config"),
        spec=CharacterConfigSpec(
            public_stats=[StatDefinition(name="cunning", type="int", default=0)],
            hidden_stats=[StatDefinition(name="legacy_power", type="int", default=0)],
        ),
    )

    return registry


@pytest.fixture
def prestige_registry() -> ContentRegistry:
    return _build_prestige_registry()


@pytest.fixture
def prestige_player(prestige_registry: ContentRegistry) -> CharacterState:
    assert prestige_registry.game is not None
    assert prestige_registry.character_config is not None
    player = CharacterState.new_character(
        name="Hero",
        game_manifest=prestige_registry.game,
        character_config=prestige_registry.character_config,
    )
    player.level = 5
    player.xp = 250
    return player


async def test_prestige_resets_level(prestige_player: CharacterState, prestige_registry: ContentRegistry) -> None:
    """Player level must be 1 after prestige."""
    tui = MockTUI()
    effect = PrestigeEffect(type="prestige")
    await run_effect(effect=effect, player=prestige_player, registry=prestige_registry, tui=tui)
    assert prestige_player.level == 1


async def test_prestige_increments_prestige_count(
    prestige_player: CharacterState, prestige_registry: ContentRegistry
) -> None:
    """Prestige count must be incremented by 1."""
    tui = MockTUI()
    effect = PrestigeEffect(type="prestige")
    await run_effect(effect=effect, player=prestige_player, registry=prestige_registry, tui=tui)
    assert prestige_player.prestige_count == 1


async def test_prestige_runs_pre_effects_before_carry(
    prestige_player: CharacterState, prestige_registry: ContentRegistry
) -> None:
    """pre_prestige_effects must run before carry snapshot; legacy_power should be 1 (0 + pre-effect +1)."""
    tui = MockTUI()
    effect = PrestigeEffect(type="prestige")
    await run_effect(effect=effect, player=prestige_player, registry=prestige_registry, tui=tui)
    # Default was 0, pre-effect adds +1, that 1 is captured in carry and restored.
    assert prestige_player.stats.get("legacy_power") == 1


async def test_prestige_carry_stat_survives_reset(
    prestige_player: CharacterState, prestige_registry: ContentRegistry
) -> None:
    """A legacy_power value set before prestige should be carried (plus pre-effect +1)."""
    prestige_player.set_stat("legacy_power", 5)
    tui = MockTUI()
    effect = PrestigeEffect(type="prestige")
    await run_effect(effect=effect, player=prestige_player, registry=prestige_registry, tui=tui)
    # 5 + 1 (pre-effect) = 6, carried through reset.
    assert prestige_player.stats.get("legacy_power") == 6


async def test_prestige_non_carry_stat_resets(
    prestige_player: CharacterState, prestige_registry: ContentRegistry
) -> None:
    """Stats not in carry_stats must revert to their config default after prestige."""
    prestige_player.set_stat("cunning", 99)
    tui = MockTUI()
    effect = PrestigeEffect(type="prestige")
    await run_effect(effect=effect, player=prestige_player, registry=prestige_registry, tui=tui)
    assert prestige_player.stats.get("cunning") == 0  # reset to StatDefinition default


async def test_prestige_sets_prestige_pending(
    prestige_player: CharacterState, prestige_registry: ContentRegistry
) -> None:
    """After prestige effect runs, prestige_pending must not be None."""
    tui = MockTUI()
    effect = PrestigeEffect(type="prestige")
    await run_effect(effect=effect, player=prestige_player, registry=prestige_registry, tui=tui)
    assert prestige_player.prestige_pending is not None


async def test_prestige_no_config_logs_error(prestige_player: CharacterState, caplog: pytest.LogCaptureFixture) -> None:
    """When no prestige config is declared in game.yaml, the handler logs an error and skips."""
    registry = ContentRegistry()
    game_without_prestige = GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="no-prestige-game"),
        spec=GameSpec(
            displayName="No Prestige",
            xp_thresholds=[100],
            hp_formula=HpFormula(base_hp=20, hp_per_level=5),
            prestige=None,
        ),
    )
    registry.game = game_without_prestige

    original_count = prestige_player.prestige_count
    tui = MockTUI()
    effect = PrestigeEffect(type="prestige")

    import logging

    with caplog.at_level(logging.ERROR):
        await run_effect(effect=effect, player=prestige_player, registry=registry, tui=tui)

    # State must not have changed.
    assert prestige_player.prestige_count == original_count
    assert prestige_player.prestige_pending is None
    assert any("prestige" in record.message.lower() for record in caplog.records)


async def test_prestige_carry_skills_preserves_known_skills() -> None:
    """Skills in carry_skills must survive the prestige reset."""
    registry = _build_prestige_registry(carry_stats=[], pre_prestige_effects=[], carry_skills=["master-swordplay"])
    assert registry.game is not None
    assert registry.character_config is not None
    player = CharacterState.new_character(
        name="Hero",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )
    player.known_skills = {"master-swordplay", "novice-archery"}

    tui = MockTUI()
    effect = PrestigeEffect(type="prestige")
    await run_effect(effect=effect, player=player, registry=registry, tui=tui)

    # Carried skill survives; non-carried skill does not.
    assert "master-swordplay" in player.known_skills
    assert "novice-archery" not in player.known_skills

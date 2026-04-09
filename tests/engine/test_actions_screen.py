"""Tests for the overworld Actions screen (open_actions_screen).

Covers all scenarios from the actions-screen spec:
  - Screen shown with overworld skills
  - Skill use dispatches effects with combat=None
  - No overworld skills → show_text, no skill menu
  - Insufficient resource blocks use
  - Adventure-scope cooldown blocks use
"""

from __future__ import annotations

from typing import List

import pytest

from oscilla.engine.actions import open_actions_screen
from oscilla.engine.character import CharacterState
from oscilla.engine.models.adventure import Cooldown, StatChangeEffect
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.character_config import CharacterConfigManifest, CharacterConfigSpec, StatDefinition
from oscilla.engine.models.game import GameManifest, GameSpec
from oscilla.engine.models.skill import SkillCost, SkillManifest, SkillSpec
from oscilla.engine.registry import ContentRegistry
from tests.engine.conftest import MockTUI

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry(extra_skills: List[SkillManifest] | None = None) -> ContentRegistry:
    """Build a minimal registry with an optional list of skill manifests."""
    registry = ContentRegistry()

    game = GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(
            displayName="Test",
        ),
    )
    registry.game = game

    char_config = CharacterConfigManifest(
        apiVersion="oscilla/v1",
        kind="CharacterConfig",
        metadata=Metadata(name="test-config"),
        spec=CharacterConfigSpec(
            public_stats=[
                StatDefinition(name="mana", type="int", default=20),
                StatDefinition(name="max_mana", type="int", default=20),
                StatDefinition(name="strength", type="int", default=10),
            ],
        ),
    )
    registry.character_config = char_config

    for skill in extra_skills or []:
        registry.skills.register(skill)

    return registry


def _make_player(registry: ContentRegistry, known_skills: List[str] | None = None) -> CharacterState:
    assert registry.game is not None
    assert registry.character_config is not None
    player = CharacterState.new_character(
        name="Tester",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )
    for ref in known_skills or []:
        player.known_skills.add(ref)
    return player


def _overworld_skill(
    name: str = "test-overworld",
    display: str = "Overworld Skill",
    cost: SkillCost | None = None,
    cooldown: Cooldown | None = None,
    use_effects: list | None = None,
) -> SkillManifest:
    return SkillManifest(
        apiVersion="oscilla/v1",
        kind="Skill",
        metadata=Metadata(name=name),
        spec=SkillSpec(
            displayName=display,
            description="An overworld skill.",
            contexts=["overworld"],
            cost=cost,
            cooldown=cooldown,
            use_effects=use_effects or [],
        ),
    )


def _combat_only_skill(name: str = "test-combat") -> SkillManifest:
    return SkillManifest(
        apiVersion="oscilla/v1",
        kind="Skill",
        metadata=Metadata(name=name),
        spec=SkillSpec(
            displayName="Combat Skill",
            description="A combat-only skill.",
            contexts=["combat"],
            use_effects=[],
        ),
    )


# ---------------------------------------------------------------------------
# Scenario: Actions screen shown with overworld skills
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actions_screen_shows_skill_menu_with_overworld_skills() -> None:
    """show_skill_menu is called when the player has at least one overworld skill."""
    skill = _overworld_skill()
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])

    tui = MockTUI()
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert len(tui.skill_menus) == 1
    assert tui.skill_menus[0][0]["name"] == "Overworld Skill"


@pytest.mark.asyncio
async def test_actions_screen_skill_dict_contains_expected_keys() -> None:
    """Skill dicts include name, description, cost_label, cooldown_label, available."""
    skill = _overworld_skill(
        cost=SkillCost(stat="mana", amount=5),
    )
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])

    tui = MockTUI()
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert len(tui.skill_menus) == 1
    entry = tui.skill_menus[0][0]
    assert entry["name"] == "Overworld Skill"
    assert "description" in entry
    assert entry["cost_label"] == "5 mana"
    assert entry["available"] is True


# ---------------------------------------------------------------------------
# Scenario: Skill used from Actions screen dispatches effects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actions_screen_dispatches_use_effects_with_combat_none() -> None:
    """Selecting a skill fires its use_effects; no CombatContext is created."""
    # XP grant would be overly complex; use a stat_change effect on mana.
    skill = _overworld_skill(
        use_effects=[StatChangeEffect(type="stat_change", stat="strength", amount=3)],
    )
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])
    initial_strength = int(player.stats["strength"])  # type: ignore[arg-type]

    # Return index 0 → select first (only) skill.
    tui = MockTUI(skill_menu_responses=[0])
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert player.stats["strength"] == initial_strength + 3
    # Confirmation text must mention the skill name.
    assert any("Overworld Skill" in t for t in tui.texts)


@pytest.mark.asyncio
async def test_actions_screen_cancel_fires_no_effects() -> None:
    """Returning None from show_skill_menu dismisses without dispatching."""
    skill = _overworld_skill(
        use_effects=[StatChangeEffect(type="stat_change", stat="strength", amount=3)],
    )
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])
    initial_strength = int(player.stats["strength"])  # type: ignore[arg-type]

    tui = MockTUI()  # No responses → returns None (cancel).
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert player.stats["strength"] == initial_strength
    assert len(tui.skill_menus) == 1  # Menu was shown but nothing dispatched.


# ---------------------------------------------------------------------------
# Scenario: Actions screen shows nothing when no overworld skills
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actions_screen_no_overworld_skills_shows_text_only() -> None:
    """When the player has only combat skills, show_text is called and show_skill_menu is not."""
    combat = _combat_only_skill()
    registry = _make_registry(extra_skills=[combat])
    player = _make_player(registry=registry, known_skills=["test-combat"])

    tui = MockTUI()
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert len(tui.skill_menus) == 0
    assert len(tui.texts) == 1
    assert "no skills" in tui.texts[0].lower()


@pytest.mark.asyncio
async def test_actions_screen_no_skills_at_all_shows_text_only() -> None:
    """When the player knows no skills, show_text is called and show_skill_menu is not."""
    registry = _make_registry()
    player = _make_player(registry=registry)

    tui = MockTUI()
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert len(tui.skill_menus) == 0
    assert len(tui.texts) == 1


# ---------------------------------------------------------------------------
# Scenario: Actions screen blocks use if resource insufficient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actions_screen_blocks_use_if_insufficient_resource() -> None:
    """Selecting a skill the player cannot afford shows an error and fires no effects."""
    skill = _overworld_skill(
        cost=SkillCost(stat="mana", amount=100),  # way more than the 20 default
        use_effects=[StatChangeEffect(type="stat_change", stat="strength", amount=99)],
    )
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])
    initial_strength = int(player.stats["strength"])  # type: ignore[arg-type]

    tui = MockTUI(skill_menu_responses=[0])
    await open_actions_screen(player=player, registry=registry, tui=tui)

    # Effects must NOT have fired.
    assert player.stats["strength"] == initial_strength
    assert any("Not enough" in t for t in tui.texts)


@pytest.mark.asyncio
async def test_actions_screen_available_false_when_insufficient_resource() -> None:
    """The skill dict marks available=False when the player cannot afford the cost."""
    skill = _overworld_skill(
        cost=SkillCost(stat="mana", amount=999),
    )
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])

    tui = MockTUI()
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert tui.skill_menus[0][0]["available"] is False


# ---------------------------------------------------------------------------
# Scenario: Actions screen blocks use if adventure-scope cooldown active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actions_screen_blocks_use_if_adventure_scope_cooldown_active() -> None:
    """Selecting a skill on cooldown shows a cooldown message and fires nothing."""
    skill = _overworld_skill(
        cooldown=Cooldown(ticks=2),
        use_effects=[StatChangeEffect(type="stat_change", stat="strength", amount=99)],
    )
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])
    # Simulate active tick-based cooldown (expires in the future).
    player.skill_tick_expiry["test-overworld"] = player.internal_ticks + 5
    initial_strength = int(player.stats["strength"])  # type: ignore[arg-type]

    tui = MockTUI(skill_menu_responses=[0])
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert player.stats["strength"] == initial_strength
    assert any("cooldown" in t.lower() for t in tui.texts)


@pytest.mark.asyncio
async def test_actions_screen_available_false_when_adventure_cooldown_active() -> None:
    """The skill dict marks available=False when cooldown is active."""
    skill = _overworld_skill(
        cooldown=Cooldown(ticks=2),
    )
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])
    player.skill_tick_expiry["test-overworld"] = player.internal_ticks + 5

    tui = MockTUI()
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert tui.skill_menus[0][0]["available"] is False


@pytest.mark.asyncio
async def test_actions_screen_records_adventure_cooldown_after_successful_use() -> None:
    """Using a skill with a tick-based cooldown sets skill_tick_expiry on the player."""
    skill = _overworld_skill(
        cooldown=Cooldown(ticks=3),
        use_effects=[],
    )
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])

    tui = MockTUI(skill_menu_responses=[0])
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert player.skill_tick_expiry["test-overworld"] == player.internal_ticks + 3


@pytest.mark.asyncio
async def test_actions_screen_deducts_mana_cost_after_successful_use() -> None:
    """Using a skill with a mana cost deducts the cost from the player's stat."""
    skill = _overworld_skill(
        cost=SkillCost(stat="mana", amount=7),
        use_effects=[],
    )
    registry = _make_registry(extra_skills=[skill])
    player = _make_player(registry=registry, known_skills=["test-overworld"])
    initial_mana = int(player.stats["mana"])  # type: ignore[arg-type]

    tui = MockTUI(skill_menu_responses=[0])
    await open_actions_screen(player=player, registry=registry, tui=tui)

    assert player.stats["mana"] == initial_mana - 7

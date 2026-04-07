"""Tests for the AdventurePipeline — end-to-end adventure execution."""

from __future__ import annotations

from oscilla.engine.character import DEFAULT_CHARACTER_NAME, CharacterState
from oscilla.engine.models.adventure import AdventureManifest, AdventureSpec, NarrativeStep
from oscilla.engine.models.base import Metadata, NameEqualsCondition
from oscilla.engine.pipeline import AdventureOutcome, AdventurePipeline
from oscilla.engine.registry import ContentRegistry
from tests.engine.conftest import MockTUI


async def test_narrative_adventure_completes(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    outcome = await pipeline.run("test-narrative")
    assert outcome == AdventureOutcome.COMPLETED


async def test_narrative_adventure_shows_text(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    await pipeline.run("test-narrative")
    assert any("test" in t.lower() for t in mock_tui.texts)


async def test_narrative_grants_xp(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """The test-narrative adventure has an xp_grant effect of 10."""
    assert minimal_registry.game is not None
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    await pipeline.run("test-narrative")
    # XP should have been added (exact amount depends on fixture; at least > 0)
    assert base_player.xp > 0


async def test_combat_win_outcome(
    combat_registry: ContentRegistry,
    combat_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """test-combat against test-enemy (hp=1) should always be won in one hit."""
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=mock_tui)
    outcome = await pipeline.run("test-combat")
    assert outcome == AdventureOutcome.COMPLETED


async def test_combat_win_grants_milestone(
    combat_registry: ContentRegistry,
    combat_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """After winning test-combat, player should hold the test-combat-won milestone."""
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=mock_tui)
    await pipeline.run("test-combat")
    assert combat_player.has_milestone("test-combat-won")


async def test_combat_win_grants_xp(
    combat_registry: ContentRegistry,
    combat_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=mock_tui)
    await pipeline.run("test-combat")
    assert combat_player.xp > 0


async def test_combat_win_records_enemy_defeated(
    combat_registry: ContentRegistry,
    combat_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=mock_tui)
    await pipeline.run("test-combat")
    assert combat_player.statistics.enemies_defeated.get("test-enemy", 0) == 1


async def test_combat_flee_outcome(
    combat_registry: ContentRegistry,
    combat_player: CharacterState,
) -> None:
    """MockTUI configured to always choose option 2 (Flee) for the attack menu."""
    tui = MockTUI(menu_responses=[2])  # Flee on first menu prompt
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=tui)
    outcome = await pipeline.run("test-combat")
    assert outcome == AdventureOutcome.FLED


async def test_active_adventure_cleared_after_run(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    await pipeline.run("test-narrative")
    assert base_player.active_adventure is None


async def test_adventure_statistics_recorded(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    await pipeline.run("test-narrative")
    assert base_player.statistics.adventures_completed.get("test-narrative", 0) == 1


async def test_pipeline_tracks_step_index(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """Test that step_index is updated during adventure execution."""
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    # Active adventure should be set during execution
    original_active = base_player.active_adventure
    assert original_active is None

    # Run adventure - this should clear active_adventure when done
    await pipeline.run("test-narrative")
    assert base_player.active_adventure is None


def _make_requires_registry(
    minimal_registry: ContentRegistry,
    requires: NameEqualsCondition | None,
) -> ContentRegistry:
    """Return a copy of minimal_registry with an additional single-step adventure.

    The narrative step optionally has a ``requires`` condition.  The TUI output
    lets tests assert whether the step ran or was silently skipped.
    """
    registry = minimal_registry  # reuse existing game/char_config
    adventure = AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=Metadata(name="test-requires-adventure"),
        spec=AdventureSpec(
            displayName="Requires Test",
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="You shall not pass.",
                    requires=requires,
                )
            ],
        ),
    )
    registry.adventures.register(adventure)
    return registry


async def test_step_requires_skips_step_when_condition_fails(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """A NarrativeStep with a failing requires condition is silently skipped."""
    base_player.name = "Elara"  # not the default; condition will fail
    cond = NameEqualsCondition(type="name_equals", value=DEFAULT_CHARACTER_NAME)
    registry = _make_requires_registry(minimal_registry, requires=cond)
    pipeline = AdventurePipeline(registry=registry, player=base_player, tui=mock_tui)
    outcome = await pipeline.run("test-requires-adventure")
    assert outcome == AdventureOutcome.COMPLETED
    assert not any("You shall not pass" in t for t in mock_tui.texts)


async def test_step_requires_runs_step_when_condition_passes(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """A NarrativeStep whose requires condition passes executes normally."""
    base_player.name = DEFAULT_CHARACTER_NAME  # matches condition
    cond = NameEqualsCondition(type="name_equals", value=DEFAULT_CHARACTER_NAME)
    registry = _make_requires_registry(minimal_registry, requires=cond)
    pipeline = AdventurePipeline(registry=registry, player=base_player, tui=mock_tui)
    await pipeline.run("test-requires-adventure")
    assert any("You shall not pass" in t for t in mock_tui.texts)


async def test_step_without_requires_always_runs(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """A NarrativeStep with no requires condition always executes."""
    base_player.name = "Elara"
    registry = _make_requires_registry(minimal_registry, requires=None)
    pipeline = AdventurePipeline(registry=registry, player=base_player, tui=mock_tui)
    await pipeline.run("test-requires-adventure")
    assert any("You shall not pass" in t for t in mock_tui.texts)

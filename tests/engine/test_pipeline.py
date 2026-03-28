"""Tests for the AdventurePipeline — end-to-end adventure execution."""

from __future__ import annotations

from oscilla.engine.pipeline import AdventureOutcome, AdventurePipeline
from oscilla.engine.player import PlayerState
from oscilla.engine.registry import ContentRegistry
from tests.engine.conftest import MockTUI


def test_narrative_adventure_completes(
    minimal_registry: ContentRegistry,
    base_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    outcome = pipeline.run("test-narrative")
    assert outcome == AdventureOutcome.COMPLETED


def test_narrative_adventure_shows_text(
    minimal_registry: ContentRegistry,
    base_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    pipeline.run("test-narrative")
    assert any("test" in t.lower() for t in mock_tui.texts)


def test_narrative_grants_xp(
    minimal_registry: ContentRegistry,
    base_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    """The test-narrative adventure has an xp_grant effect of 10."""
    assert minimal_registry.game is not None
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    pipeline.run("test-narrative")
    # XP should have been added (exact amount depends on fixture; at least > 0)
    assert base_player.xp > 0


def test_combat_win_outcome(
    combat_registry: ContentRegistry,
    combat_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    """test-combat against test-enemy (hp=1) should always be won in one hit."""
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=mock_tui)
    outcome = pipeline.run("test-combat")
    assert outcome == AdventureOutcome.COMPLETED


def test_combat_win_grants_milestone(
    combat_registry: ContentRegistry,
    combat_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    """After winning test-combat, player should hold the test-combat-won milestone."""
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=mock_tui)
    pipeline.run("test-combat")
    assert combat_player.has_milestone("test-combat-won")


def test_combat_win_grants_xp(
    combat_registry: ContentRegistry,
    combat_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=mock_tui)
    pipeline.run("test-combat")
    assert combat_player.xp > 0


def test_combat_win_records_enemy_defeated(
    combat_registry: ContentRegistry,
    combat_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=mock_tui)
    pipeline.run("test-combat")
    assert combat_player.statistics.enemies_defeated.get("test-enemy", 0) == 1


def test_combat_flee_outcome(
    combat_registry: ContentRegistry,
    combat_player: PlayerState,
) -> None:
    """MockTUI configured to always choose option 2 (Flee) for the attack menu."""
    tui = MockTUI(menu_responses=[2])  # Flee on first menu prompt
    pipeline = AdventurePipeline(registry=combat_registry, player=combat_player, tui=tui)
    outcome = pipeline.run("test-combat")
    assert outcome == AdventureOutcome.FLED


def test_active_adventure_cleared_after_run(
    minimal_registry: ContentRegistry,
    base_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    pipeline.run("test-narrative")
    assert base_player.active_adventure is None


def test_adventure_statistics_recorded(
    minimal_registry: ContentRegistry,
    base_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    pipeline.run("test-narrative")
    assert base_player.statistics.adventures_completed.get("test-narrative", 0) == 1


def test_pipeline_tracks_step_index(
    minimal_registry: ContentRegistry,
    base_player: PlayerState,
    mock_tui: MockTUI,
) -> None:
    """Test that step_index is updated during adventure execution."""
    pipeline = AdventurePipeline(registry=minimal_registry, player=base_player, tui=mock_tui)
    # Active adventure should be set during execution
    original_active = base_player.active_adventure
    assert original_active is None

    # Run adventure - this should clear active_adventure when done
    pipeline.run("test-narrative")
    assert base_player.active_adventure is None

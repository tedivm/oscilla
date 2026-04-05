"""Integration tests for the in-game time system.

Uses the tests/fixtures/content/ingame-time/ content package and the
ingame_time_registry fixture to exercise the full pipeline-to-condition
evaluation flow end-to-end.

The fixture game has:
  - Root cycle: test-tick
  - Derived: test-hour (count=4, labels Dawn/Noon/Dusk/Midnight, alias: hour)
  - Derived: test-day  (count=3, labels Monday/Tuesday/Wednesday)
  - ticks_per_adventure: 1
  - Epoch: {test-hour: 1}  (display starts at Dawn)
  - Era test-era-always   (always active, tracks test-day, epoch_count=1)
  - Era test-era-conditional (level>=2 start, level>=5 end, tracks test-day)
"""

from __future__ import annotations

import pytest

from oscilla.engine.character import CharacterState
from oscilla.engine.conditions import evaluate
from oscilla.engine.models.adventure import (
    AdjustGameTicksEffect,
    AdventureManifest,
    AdventureSpec,
    EndAdventureEffect,
    NarrativeStep,
)
from oscilla.engine.models.base import GameCalendarCycleCondition, GameCalendarEraCondition, Metadata
from oscilla.engine.pipeline import AdventurePipeline
from oscilla.engine.registry import ContentRegistry
from tests.engine.conftest import MockTUI

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(registry: ContentRegistry) -> CharacterState:
    assert registry.game is not None
    assert registry.character_config is not None
    return CharacterState.new_character(
        name="IntegTester",
        game_manifest=registry.game,
        character_config=registry.character_config,
    )


def _adjust_ticks_adventure(name: str, delta: int) -> AdventureManifest:
    """Build an adventure that fires adjust_game_ticks with the given delta."""
    return AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=Metadata(name=name),
        spec=AdventureSpec(
            displayName=name,
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="Adjusting time...",
                    effects=[AdjustGameTicksEffect(type="adjust_game_ticks", delta=delta)],
                ),
                NarrativeStep(
                    type="narrative",
                    text="Done.",
                    effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                ),
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Full pipeline tick advancement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_advances_both_clocks(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """Running test-narrative through the full pipeline advances both clocks by 1."""
    player = _make_player(ingame_time_registry)
    assert player.internal_ticks == 0
    assert player.game_ticks == 0

    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    await pipeline.run("test-narrative")

    assert player.internal_ticks == 1
    assert player.game_ticks == 1
    assert player.adventure_last_completed_at_ticks["test-narrative"] == 1


@pytest.mark.asyncio
async def test_pipeline_multiple_runs_accumulate_ticks(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """Running test-narrative three times accumulates ticks on both clocks."""
    player = _make_player(ingame_time_registry)
    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    for _ in range(3):
        await pipeline.run("test-narrative")

    assert player.internal_ticks == 3
    assert player.game_ticks == 3


# ---------------------------------------------------------------------------
# game_calendar_cycle_is condition via ingame_time_registry resolver
# ---------------------------------------------------------------------------


def test_cycle_condition_allows_at_correct_label(
    ingame_time_registry: ContentRegistry,
) -> None:
    """game_calendar_cycle_is passes when the cycle is at the expected label.

    The fixture epoch starts the display at Dawn (test-hour position 0 = Dawn at tick 0).
    """
    player = _make_player(ingame_time_registry)
    # At game_ticks=0 epoch-adjusted position is Dawn.
    player.game_ticks = 0
    player.internal_ticks = 0

    cond = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="test-hour", value="Dawn")
    result = evaluate(condition=cond, player=player, registry=ingame_time_registry)
    assert result is True


def test_cycle_condition_blocks_at_wrong_label(
    ingame_time_registry: ContentRegistry,
) -> None:
    """game_calendar_cycle_is fails when the cycle is at a different label."""
    player = _make_player(ingame_time_registry)
    player.game_ticks = 0
    player.internal_ticks = 0

    cond = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="test-hour", value="Midnight")
    result = evaluate(condition=cond, player=player, registry=ingame_time_registry)
    assert result is False


def test_cycle_condition_advances_to_next_label_after_tick(
    ingame_time_registry: ContentRegistry,
) -> None:
    """After advancing game_ticks by 1, the cycle label moves to the next position."""
    player = _make_player(ingame_time_registry)
    # At game_ticks=0 display is Dawn; at game_ticks=1 display should be Noon.
    player.game_ticks = 1
    player.internal_ticks = 1

    cond_dawn = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="test-hour", value="Dawn")
    cond_noon = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="test-hour", value="Noon")
    assert evaluate(condition=cond_dawn, player=player, registry=ingame_time_registry) is False
    assert evaluate(condition=cond_noon, player=player, registry=ingame_time_registry) is True


def test_cycle_alias_resolves_correctly(
    ingame_time_registry: ContentRegistry,
) -> None:
    """The alias 'hour' for 'test-hour' resolves to the same cycle state."""
    player = _make_player(ingame_time_registry)
    player.game_ticks = 0
    player.internal_ticks = 0

    cond_alias = GameCalendarCycleCondition(type="game_calendar_cycle_is", cycle="hour", value="Dawn")
    assert evaluate(condition=cond_alias, player=player, registry=ingame_time_registry) is True


# ---------------------------------------------------------------------------
# game_calendar_era_is condition via ingame_time_registry resolver
# ---------------------------------------------------------------------------


def test_era_condition_always_active_era(
    ingame_time_registry: ContentRegistry,
) -> None:
    """test-era-always is active at tick 0 (no start condition required)."""
    player = _make_player(ingame_time_registry)

    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="test-era-always", state="active")
    assert evaluate(condition=cond, player=player, registry=ingame_time_registry) is True


def test_era_condition_conditional_era_inactive_before_start(
    ingame_time_registry: ContentRegistry,
) -> None:
    """test-era-conditional is inactive at level 1 (start_condition requires level 2)."""
    player = _make_player(ingame_time_registry)
    assert player.level == 1

    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="test-era-conditional", state="active")
    assert evaluate(condition=cond, player=player, registry=ingame_time_registry) is False


def test_era_condition_conditional_era_active_after_latch(
    ingame_time_registry: ContentRegistry,
) -> None:
    """test-era-conditional becomes active once era_started_at_ticks is set (latch fires)."""
    player = _make_player(ingame_time_registry)
    # Simulate the latch having fired: record start but not end.
    player.era_started_at_ticks["test-era-conditional"] = 5

    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="test-era-conditional", state="active")
    assert evaluate(condition=cond, player=player, registry=ingame_time_registry) is True


def test_era_condition_conditional_era_inactive_after_end_latch(
    ingame_time_registry: ContentRegistry,
) -> None:
    """test-era-conditional is inactive once era_ended_at_ticks is also set."""
    player = _make_player(ingame_time_registry)
    player.era_started_at_ticks["test-era-conditional"] = 5
    player.era_ended_at_ticks["test-era-conditional"] = 20

    cond = GameCalendarEraCondition(type="game_calendar_era_is", era="test-era-conditional", state="active")
    assert evaluate(condition=cond, player=player, registry=ingame_time_registry) is False


# ---------------------------------------------------------------------------
# adjust_game_ticks effect in full pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adjust_game_ticks_updates_game_ticks_not_internal(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """adjust_game_ticks delta is applied to game_ticks but does not touch internal_ticks.

    After running a pipeline there are two sources of game_ticks change:
      - the normal tick cost (ticks_per_adventure = 1): adds 1 to both clocks
      - the adjust_game_ticks effect (delta = +5): adds 5 only to game_ticks

    So internal_ticks should be 1, game_ticks should be 6.
    """
    adv = _adjust_ticks_adventure(name="test-adjust-integration", delta=5)
    ingame_time_registry.adventures.register(adv)

    player = _make_player(ingame_time_registry)
    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    await pipeline.run("test-adjust-integration")

    assert player.internal_ticks == 1
    assert player.game_ticks == 6


@pytest.mark.asyncio
async def test_adjust_game_ticks_clamps_at_zero(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """A large negative delta clamps game_ticks at zero (pre_epoch_behavior: clamp).

    Execution order: effect fires during steps (game_ticks is clamped to 0), then
    the pipeline adds the normal tick cost (1) on completion.  Final value is 1.
    """
    adv = _adjust_ticks_adventure(name="test-adjust-negative", delta=-999)
    ingame_time_registry.adventures.register(adv)

    player = _make_player(ingame_time_registry)
    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    await pipeline.run("test-adjust-negative")

    # effect clamps to 0, then tick_cost=1 is added → final game_ticks=1
    assert player.game_ticks == 1
    # internal_ticks is never modified by adjust_game_ticks
    assert player.internal_ticks == 1


# ---------------------------------------------------------------------------
# Cooldown uses adventure_last_completed_at_ticks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cooldown_ticks_blocks_after_recent_completion(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """An adventure with cooldown_ticks=3 is ineligible immediately after completion."""
    cooldown_adv = AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=Metadata(name="test-cooldown-integration"),
        spec=AdventureSpec(
            displayName="Cooldown Adventure",
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="Done.",
                    effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                ),
            ],
            cooldown_ticks=3,
            repeatable=True,
        ),
    )
    ingame_time_registry.adventures.register(cooldown_adv)

    player = _make_player(ingame_time_registry)
    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    await pipeline.run("test-cooldown-integration")

    # After 1 tick internal_ticks=1; last_completed=1; cooldown=3 → ineligible
    from datetime import date

    assert player.adventure_last_completed_at_ticks["test-cooldown-integration"] == 1
    eligible = player.is_adventure_eligible(
        adventure_ref="test-cooldown-integration",
        spec=cooldown_adv.spec,
        today=date.today(),
    )
    assert eligible is False


@pytest.mark.asyncio
async def test_cooldown_ticks_allows_after_enough_ticks_elapsed(
    ingame_time_registry: ContentRegistry,
    mock_tui: MockTUI,
) -> None:
    """An adventure with cooldown_ticks=3 becomes eligible after 3 more ticks pass."""
    cooldown_adv = AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=Metadata(name="test-cooldown-allow"),
        spec=AdventureSpec(
            displayName="Cooldown Allow",
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="Done.",
                    effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                ),
            ],
            cooldown_ticks=3,
            repeatable=True,
        ),
    )
    ingame_time_registry.adventures.register(cooldown_adv)

    player = _make_player(ingame_time_registry)
    pipeline = AdventurePipeline(
        registry=ingame_time_registry,
        player=player,
        tui=mock_tui,
    )
    await pipeline.run("test-cooldown-allow")
    # Now run test-narrative 3 more times to advance ticks past the cooldown
    for _ in range(3):
        await pipeline.run("test-narrative")

    from datetime import date

    # internal_ticks=4; last_completed=1; 4-1=3 >= cooldown_ticks=3 → eligible
    eligible = player.is_adventure_eligible(
        adventure_ref="test-cooldown-allow",
        spec=cooldown_adv.spec,
        today=date.today(),
    )
    assert eligible is True

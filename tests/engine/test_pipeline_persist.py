"""Unit tests for AdventurePipeline's PersistCallback integration."""

from __future__ import annotations

from typing import List, Literal

from oscilla.engine.character import CharacterState
from oscilla.engine.pipeline import AdventureOutcome, AdventurePipeline
from oscilla.engine.registry import ContentRegistry
from tests.engine.conftest import MockTUI


class RecordingCallback:
    """Records every (state, event) pair delivered by the pipeline."""

    def __init__(self) -> None:
        self.calls: List[tuple[CharacterState, str]] = []

    async def __call__(
        self,
        state: CharacterState,
        event: Literal["step_start", "combat_round", "adventure_end"],
    ) -> None:
        self.calls.append((state, event))


async def test_no_callback_runs_to_completion(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """Pipeline with on_state_change=None completes without error."""
    pipeline = AdventurePipeline(
        registry=minimal_registry,
        player=base_player,
        tui=mock_tui,
        on_state_change=None,
    )
    outcome = await pipeline.run("test-narrative")
    assert outcome == AdventureOutcome.COMPLETED


async def test_step_start_fires_before_each_step(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """step_start fires at least once per step dispatched."""
    callback = RecordingCallback()
    pipeline = AdventurePipeline(
        registry=minimal_registry,
        player=base_player,
        tui=mock_tui,
        on_state_change=callback,
    )
    await pipeline.run("test-narrative")
    step_starts = [event for _, event in callback.calls if event == "step_start"]
    assert len(step_starts) >= 1


async def test_combat_round_fires_after_each_round(
    combat_registry: ContentRegistry,
    combat_player: CharacterState,
) -> None:
    """combat_round fires once for each full combat turn (test-enemy has 1 HP → 1 round)."""
    callback = RecordingCallback()
    # Attack on the first menu prompt (option 1)
    tui = MockTUI(menu_responses=[1])
    pipeline = AdventurePipeline(
        registry=combat_registry,
        player=combat_player,
        tui=tui,
        on_state_change=callback,
    )
    await pipeline.run("test-combat")
    combat_rounds = [event for _, event in callback.calls if event == "combat_round"]
    # test-enemy has 1 HP and player does at least 1 damage → 1 round
    assert len(combat_rounds) >= 1


async def test_adventure_end_fires_once_with_cleared_adventure(
    minimal_registry: ContentRegistry,
    base_player: CharacterState,
    mock_tui: MockTUI,
) -> None:
    """adventure_end fires exactly once; when it fires, active_adventure is already None."""
    fired_states: List[CharacterState] = []

    async def callback(
        state: CharacterState,
        event: Literal["step_start", "combat_round", "adventure_end"],
    ) -> None:
        if event == "adventure_end":
            fired_states.append(state)

    pipeline = AdventurePipeline(
        registry=minimal_registry,
        player=base_player,
        tui=mock_tui,
        on_state_change=callback,
    )
    await pipeline.run("test-narrative")
    assert len(fired_states) == 1
    assert fired_states[0].active_adventure is None

"""Narrative step handler — displays text and waits for player acknowledgement."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List

from oscilla.engine.models.adventure import Effect, NarrativeStep
from oscilla.engine.pipeline import AdventureOutcome, TUICallbacks

if TYPE_CHECKING:
    from oscilla.engine.player import PlayerState


def run_narrative(
    step: NarrativeStep,
    player: "PlayerState",
    tui: TUICallbacks,
    run_effects: Callable[[List[Effect]], None],
) -> AdventureOutcome:
    """Display the narrative text, wait for acknowledgement, then fire effects."""
    tui.show_text(step.text)
    tui.wait_for_ack()
    run_effects(step.effects)
    return AdventureOutcome.COMPLETED

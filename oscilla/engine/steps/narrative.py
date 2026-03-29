"""Narrative step handler — displays text and waits for player acknowledgement."""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable, List

from oscilla.engine.models.adventure import Effect, NarrativeStep
from oscilla.engine.pipeline import AdventureOutcome, TUICallbacks

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState


async def run_narrative(
    step: NarrativeStep,
    player: "CharacterState",
    tui: TUICallbacks,
    run_effects: Callable[[List[Effect]], Awaitable[None]],
) -> AdventureOutcome:
    """Display the narrative text, wait for acknowledgement, then fire effects."""
    await tui.show_text(step.text)
    await tui.wait_for_ack()
    await run_effects(step.effects)
    return AdventureOutcome.COMPLETED

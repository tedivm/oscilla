"""Narrative step handler — displays text and waits for player acknowledgement."""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable, List

from oscilla.engine.models.adventure import Effect, NarrativeStep
from oscilla.engine.pipeline import AdventureOutcome, UICallbacks
from oscilla.engine.templates import ExpressionContext

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry


async def run_narrative(
    step: NarrativeStep,
    player: "CharacterState",
    tui: UICallbacks,
    run_effects: Callable[[List[Effect]], Awaitable[None]],
    registry: "ContentRegistry",
    ctx: ExpressionContext,
) -> AdventureOutcome:
    """Display the narrative text, wait for acknowledgement, then fire effects."""
    text = step.text
    engine = registry.template_engine
    if engine is not None and engine.is_template(text):
        template_id = f"__narrative_{id(step)}"
        text = engine.render(template_id, ctx)
    await tui.show_text(text)
    await tui.wait_for_ack()
    await run_effects(step.effects)
    return AdventureOutcome.COMPLETED

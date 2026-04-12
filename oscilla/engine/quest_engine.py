"""Quest progression engine — stage advancement and completion handling."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from oscilla.engine.conditions import evaluate

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.pipeline import UICallbacks
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)


def _advance_quests_silent(player: "CharacterState", registry: "ContentRegistry") -> None:
    """Sync, no-effect advancement used on character load.

    Re-evaluates every active quest against the player's current milestone set.
    Advances stages and marks quests complete without running any completion_effects.
    This corrects state that may be out of sync due to the milestone being granted
    before the quest was activated, or due to bugs in previous sessions.
    """
    if not player.active_quests:
        return

    # Work on a copy — we may complete quests mid-iteration.
    to_advance = dict(player.active_quests)
    for quest_ref, stage_name in list(to_advance.items()):
        quest_manifest = registry.quests.get(quest_ref)
        if quest_manifest is None:
            logger.warning("Active quest %r not found in registry — skipping advancement.", quest_ref)
            continue
        stage_map = {s.name: s for s in quest_manifest.spec.stages}
        current_stage_name = stage_name

        # Walk forward as far as milestones allow (handles chained immediate advancements
        # when multiple advance_on milestones are already held at load time).
        while True:
            stage = stage_map.get(current_stage_name)
            if stage is None:
                logger.error(
                    "Quest %r references unknown stage %r — stopping advancement.",
                    quest_ref,
                    current_stage_name,
                )
                break
            if stage.terminal:
                # Quest is already at terminal — mark complete, remove from active.
                player.active_quests.pop(quest_ref, None)
                player.completed_quests.add(quest_ref)
                break
            # Check if any advance_on milestone is satisfied.
            triggered = next((m for m in stage.advance_on if player.has_milestone(m)), None)
            if triggered is None:
                break  # No advancement possible yet.
            next_stage_name = stage.next_stage
            if next_stage_name is None:
                # Model validator should prevent this, but guard defensively.
                logger.error(
                    "Quest %r stage %r has no next_stage but is not terminal.",
                    quest_ref,
                    current_stage_name,
                )
                break
            logger.debug(
                "Quest %r: silent advance %r → %r (milestone %r).",
                quest_ref,
                current_stage_name,
                next_stage_name,
                triggered,
            )
            player.active_quests[quest_ref] = next_stage_name
            current_stage_name = next_stage_name

    # After advancing, silently fail any quests whose fail_condition is now met.
    _fail_quests_silent(player=player, registry=registry)


def _fail_quests_silent(player: "CharacterState", registry: "ContentRegistry") -> None:
    """Move any active quests whose fail_condition is met to failed_quests.

    No fail_effects are run — this is the silent correction used on character load.
    """
    for quest_ref in list(player.active_quests):
        quest_manifest = registry.quests.get(quest_ref)
        if quest_manifest is None:
            continue
        stage_name = player.active_quests[quest_ref]
        stage_map = {s.name: s for s in quest_manifest.spec.stages}
        stage = stage_map.get(stage_name)
        if stage is None or stage.fail_condition is None:
            continue
        if evaluate(condition=stage.fail_condition, player=player, registry=registry):
            logger.debug("Quest %r: silently failed at stage %r.", quest_ref, stage_name)
            player.active_quests.pop(quest_ref)
            player.failed_quests.add(quest_ref)


async def evaluate_quest_advancements(
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "UICallbacks",
) -> None:
    """Async, full-effect advancement used after milestone_grant at runtime.

    Evaluates all active quests against the player's current milestone set,
    advances stages, and executes completion_effects on terminal stages.
    Multiple chained advancements (where the moved-to stage also has its
    advance_on milestone already held) are followed in a single call.
    """
    # Local import avoids circular dependency: quest_engine ← effects ← quest_engine.
    from oscilla.engine.steps.effects import run_effect

    if not player.active_quests:
        return

    to_advance = dict(player.active_quests)
    for quest_ref, stage_name in list(to_advance.items()):
        quest_manifest = registry.quests.get(quest_ref)
        if quest_manifest is None:
            logger.warning("Active quest %r not found in registry — skipping advancement.", quest_ref)
            continue
        stage_map = {s.name: s for s in quest_manifest.spec.stages}
        current_stage_name = stage_name

        while True:
            stage = stage_map.get(current_stage_name)
            if stage is None:
                logger.error(
                    "Quest %r references unknown stage %r — stopping.",
                    quest_ref,
                    current_stage_name,
                )
                break
            if stage.terminal:
                # Run completion effects, then mark complete.
                player.active_quests.pop(quest_ref, None)
                player.completed_quests.add(quest_ref)
                display_name = quest_manifest.spec.displayName
                await tui.show_text(f"[bold green]Quest complete: {display_name}[/bold green]")
                for effect in stage.completion_effects:
                    await run_effect(effect=effect, player=player, registry=registry, tui=tui)
                break
            triggered = next((m for m in stage.advance_on if player.has_milestone(m)), None)
            if triggered is None:
                break
            next_stage_name = stage.next_stage
            if next_stage_name is None:
                logger.error(
                    "Quest %r stage %r has no next_stage but is not terminal.",
                    quest_ref,
                    current_stage_name,
                )
                break
            logger.debug(
                "Quest %r: advance %r → %r (milestone %r).",
                quest_ref,
                current_stage_name,
                next_stage_name,
                triggered,
            )
            player.active_quests[quest_ref] = next_stage_name
            current_stage_name = next_stage_name

    # After advancing, check for any quest failures.
    await _evaluate_quest_failures(player=player, registry=registry, tui=tui)


async def _evaluate_quest_failures(
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "UICallbacks",
) -> None:
    """Move any active quests whose fail_condition is met to failed_quests.

    Runs fail_effects from the stage that was active when the quest failed.
    """
    # Local import to avoid circular dependency: quest_engine ← effects ← quest_engine.
    from oscilla.engine.steps.effects import run_effect

    for quest_ref in list(player.active_quests):
        quest_manifest = registry.quests.get(quest_ref)
        if quest_manifest is None:
            continue
        stage_name = player.active_quests[quest_ref]
        stage_map = {s.name: s for s in quest_manifest.spec.stages}
        stage = stage_map.get(stage_name)
        if stage is None or stage.fail_condition is None:
            continue
        if evaluate(condition=stage.fail_condition, player=player, registry=registry):
            player.active_quests.pop(quest_ref)
            player.failed_quests.add(quest_ref)
            display_name = quest_manifest.spec.displayName
            await tui.show_text(f"[bold red]Quest failed: {display_name}[/bold red]")
            for effect in stage.fail_effects:
                await run_effect(effect=effect, player=player, registry=registry, tui=tui)

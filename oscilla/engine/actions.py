"""Overworld (out-of-combat) action helpers.

``open_actions_screen`` is the primary entry point: it presents the player
with the skills they can activate outside combat and dispatches the chosen
one, performing the same pre-use checks as the combat skill handler.
"""

from __future__ import annotations

import time
from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.models.adventure import Cooldown
    from oscilla.engine.pipeline import UICallbacks
    from oscilla.engine.registry import ContentRegistry
    from oscilla.engine.templates import GameTemplateEngine

logger = getLogger(__name__)


def _skill_on_cooldown(player: "CharacterState", skill_ref: str) -> bool:
    """Return True if a persistent (adventure-scope) cooldown is active for skill_ref."""
    now_ticks = player.internal_ticks
    now_ts = int(time.time())
    tick_exp = player.skill_tick_expiry.get(skill_ref)
    real_exp = player.skill_real_expiry.get(skill_ref)
    if tick_exp is not None and now_ticks < tick_exp:
        return True
    if real_exp is not None and now_ts < real_exp:
        return True
    return False


def _set_skill_cooldown(
    player: "CharacterState",
    skill_ref: str,
    cooldown: "Cooldown",
    template_engine: "GameTemplateEngine | None" = None,
) -> None:
    """Record expiry values on player state for a skill that was just used.

    Sets skill_tick_expiry and/or skill_real_expiry from the cooldown's ticks/seconds
    fields. The game_ticks field is not supported for skills and is logged and ignored.
    Template strings in field values are resolved via template_engine if provided.
    """

    def _resolve(v: Any) -> int | None:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if template_engine is not None:
            try:
                rendered = template_engine.render_raw(v)
                return int(rendered)
            except Exception:
                logger.warning(
                    "Failed to render cooldown template %r for skill %r — skipping constraint.",
                    v,
                    skill_ref,
                )
        return None

    now_ticks = player.internal_ticks
    now_ts = int(time.time())

    ticks = _resolve(cooldown.ticks)
    if ticks is not None:
        player.skill_tick_expiry[skill_ref] = now_ticks + ticks

    seconds = _resolve(cooldown.seconds)
    if seconds is not None:
        player.skill_real_expiry[skill_ref] = now_ts + seconds

    if cooldown.game_ticks is not None:
        logger.warning("game_ticks cooldown for skill %r is not supported; ignoring.", skill_ref)


async def open_actions_screen(
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "UICallbacks",
) -> None:
    """Present the overworld Actions screen and dispatch the selected skill.

    1. Collects skills whose ``contexts`` includes ``"overworld"``.
    2. Builds a display dict for each skill and shows the menu.
    3. If the player selects a skill, validates resource cost, ``requires``
       condition, and adventure-scope cooldown before dispatching
       ``use_effects`` with ``combat=None``.
    4. Errors and cooldown messages are surfaced via ``tui.show_text`` so the
       caller never needs to inspect the return value.
    """
    from oscilla.engine.conditions import evaluate
    from oscilla.engine.steps.effects import run_effect

    # --- Collect overworld skills -----------------------------------------
    all_refs = player.available_skills(registry=registry)
    overworld_refs: List[str] = []
    for ref in sorted(all_refs):  # deterministic ordering
        skill_m = registry.skills.get(ref)
        if skill_m is not None and "overworld" in skill_m.spec.contexts:
            overworld_refs.append(ref)

    if not overworld_refs:
        await tui.show_text("You have no skills available outside of combat.")
        return

    # --- Build display dicts ----------------------------------------------
    skill_dicts: List[Dict[str, object]] = []
    for ref in overworld_refs:
        skill_m = registry.skills.get(ref)
        if skill_m is None:
            continue
        spec = skill_m.spec

        cost_label: str | None = None
        if spec.cost is not None:
            cost_label = f"{spec.cost.amount} {spec.cost.stat}"

        cooldown_label: str | None = None
        if spec.cooldown is not None:
            if spec.cooldown.scope == "turn":
                cooldown_label = f"Every {spec.cooldown.turns} turn(s) (combat only)"
            else:
                if _skill_on_cooldown(player=player, skill_ref=ref):
                    cooldown_label = "On cooldown"
                else:
                    parts: List[str] = []
                    if spec.cooldown.ticks is not None:
                        parts.append(f"{spec.cooldown.ticks} tick(s)")
                    if spec.cooldown.game_ticks is not None:
                        parts.append(f"{spec.cooldown.game_ticks} game tick(s)")
                    if spec.cooldown.seconds is not None:
                        parts.append(f"{spec.cooldown.seconds}s")
                    cooldown_label = ("Once per " + " / ".join(parts)) if parts else "Cooldown"

        # Determine whether the skill can be used right now.
        available = True
        if spec.cost is not None:
            current = player.stats.get(spec.cost.stat, 0)
            if not isinstance(current, int) or isinstance(current, bool) or current < spec.cost.amount:
                available = False
        if spec.cooldown is not None and spec.cooldown.scope != "turn":
            if _skill_on_cooldown(player=player, skill_ref=ref):
                available = False
        if not evaluate(condition=spec.requires, player=player, registry=registry):
            available = False

        skill_dicts.append(
            {
                "name": spec.displayName,
                "description": spec.description,
                "cost_label": cost_label,
                "cooldown_label": cooldown_label,
                "available": available,
            }
        )

    # --- Show the menu -----------------------------------------------------
    # show_skill_menu returns a 0-based index or None for cancel.
    selection = await tui.show_skill_menu(skill_dicts)
    if selection is None:
        return

    if selection < 0 or selection >= len(overworld_refs):
        logger.warning("show_skill_menu returned out-of-range index %d — ignoring.", selection)
        return

    skill_ref = overworld_refs[selection]
    skill_m = registry.skills.get(skill_ref)
    if skill_m is None:
        await tui.show_text(f"[red]Error: skill {skill_ref!r} not found in registry.[/red]")
        return

    spec = skill_m.spec

    # --- Pre-use validation (mirrors _use_skill_in_combat) -----------------

    # Adventure-scope cooldown check (turn-scope cooldowns are combat-only).
    if spec.cooldown is not None and spec.cooldown.scope != "turn":
        if _skill_on_cooldown(player=player, skill_ref=skill_ref):
            await tui.show_text(f"[yellow]{spec.displayName} is on cooldown.[/yellow]")
            return

    # Resource cost check.
    if spec.cost is not None:
        current = player.stats.get(spec.cost.stat, 0)
        if not isinstance(current, int) or isinstance(current, bool):
            await tui.show_text(f"[red]Error: resource stat {spec.cost.stat!r} is not numeric.[/red]")
            return
        if current < spec.cost.amount:
            await tui.show_text(
                f"[red]Not enough {spec.cost.stat} to use {spec.displayName} "
                f"(need {spec.cost.amount}, have {current}).[/red]"
            )
            return

    # Activation condition check.
    if not evaluate(condition=spec.requires, player=player, registry=registry):
        await tui.show_text(f"[red]You cannot use {spec.displayName} right now.[/red]")
        return

    # --- Deduct cost and record cooldown -----------------------------------
    if spec.cost is not None:
        old = int(player.stats.get(spec.cost.stat) or 0)
        player.set_stat(name=spec.cost.stat, value=old - spec.cost.amount)

    if spec.cooldown is not None and spec.cooldown.scope != "turn":
        _set_skill_cooldown(player=player, skill_ref=skill_ref, cooldown=spec.cooldown)

    # --- Dispatch use_effects with combat=None ----------------------------
    await tui.show_text(f"You use [bold]{spec.displayName}[/bold]!")
    for eff in spec.use_effects:
        await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=None)

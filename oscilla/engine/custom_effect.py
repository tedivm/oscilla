"""Runtime dispatcher for CustomEffect manifests."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.combat_context import CombatContext
    from oscilla.engine.pipeline import UICallbacks
    from oscilla.engine.registry import ContentRegistry
    from oscilla.engine.templates import ExpressionContext


logger = getLogger(__name__)


async def run_custom_effect(
    ce_name: str,
    call_params: Dict[str, Any],
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "UICallbacks",
    combat: "CombatContext | None" = None,
    ctx: "ExpressionContext | None" = None,
) -> None:
    """Execute a CustomEffect by name, merging defaults and injecting params.

    Looks up the CustomEffect manifest in the registry, merges the manifest's
    parameter defaults with the call-site overrides, injects ``params`` into
    the ``ExpressionContext``, and executes each body effect sequentially.
    """
    from oscilla.engine.templates import CombatContextView, ExpressionContext, GameContext, PlayerContext

    ce_manifest = registry.custom_effects.get(ce_name)
    if ce_manifest is None:
        logger.error("custom_effect: %r not found in registry — skipping.", ce_name)
        await tui.show_text(f"[red]Error: custom effect {ce_name!r} not found.[/red]")
        return

    # Build merged params: manifest defaults overridden by call-site values.
    defaults: Dict[str, int | float | str | bool] = {
        p.name: p.default for p in ce_manifest.spec.parameters if p.default is not None
    }
    merged_params: Dict[str, int | float | str | bool] = {**defaults, **call_params}

    # Inject params into the ExpressionContext for body effect template resolution.
    if ctx is None:
        game_spec = registry.game.spec if registry.game is not None else None
        hemisphere = game_spec.season_hemisphere if game_spec is not None else "northern"
        timezone = game_spec.timezone if game_spec is not None else None
        combat_view: CombatContextView | None = None
        if combat is not None:
            enemy_ref = getattr(combat, "enemy_ref", "")
            enemy_manifest = registry.enemies.get(enemy_ref)
            enemy_name = enemy_manifest.spec.displayName if enemy_manifest is not None else enemy_ref
            combat_view = CombatContextView(
                enemy_stats=dict(combat.enemy_stats),
                enemy_name=enemy_name,
                turn=combat.turn_number,
                combat_stats=dict(combat.combat_stats),
            )
        ctx = ExpressionContext(
            player=PlayerContext.from_character(player),
            game=GameContext(season_hemisphere=hemisphere, timezone=timezone),
            combat=combat_view,
            params=merged_params,
        )
    else:
        # Copy the context with params injected, preserving all other fields.
        ctx = ExpressionContext(
            player=ctx.player,
            combat=ctx.combat,
            game=ctx.game,
            ingame_time=ctx.ingame_time,
            this=ctx.this,
            params=merged_params,
        )

    # Execute each effect in the body sequentially.
    for body_effect in ce_manifest.spec.effects:
        from oscilla.engine.steps.effects import run_effect

        await run_effect(
            effect=body_effect,
            player=player,
            registry=registry,
            tui=tui,
            combat=combat,
            ctx=ctx,
        )

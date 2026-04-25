"""Combat step handler — turn-based fight loop with skill support."""

from __future__ import annotations

import time
from logging import getLogger
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Literal, Set

from oscilla.engine.combat_context import ActiveCombatEffect, CombatContext
from oscilla.engine.models.adventure import ApplyBuffEffect, CombatStep, ItemDropEffect, OutcomeBranch
from oscilla.engine.models.buff import StoredBuff
from oscilla.engine.pipeline import AdventureOutcome, UICallbacks
from oscilla.engine.steps.effects import run_effect
from oscilla.engine.templates import CombatFormulaContext, FormulaRenderError, render_formula

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.models.combat_system import CombatStepOverrides, CombatSystemSpec, DamageFormulaEntry
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)


async def _tick_active_effects(
    ctx: CombatContext,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: UICallbacks,
) -> None:
    """Fire per-turn effects for all active periodic effects, then expire finished ones.

    Called at the top of each combat round before the player acts.
    """
    expired: List[int] = []
    for i, ae in enumerate(ctx.active_effects):
        if ae.per_turn_effects:
            await tui.show_text(f"[italic]{ae.source_skill}[/italic] ticks ({ae.remaining_turns} turn(s) left).")
            for eff in ae.per_turn_effects:
                await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)
        ae.remaining_turns -= 1
        if ae.remaining_turns <= 0:
            expired.append(i)
    # Remove expired in reverse order to preserve indices.
    for i in reversed(expired):
        ctx.active_effects.pop(i)


def _apply_damage_amplify(base: int, target: Literal["player", "enemy"], ctx: CombatContext) -> int:
    """Scale outgoing damage by any damage_amplify modifiers active for target.

    All active damage_amplify modifiers for the named target are summed and applied
    as a single multiplicative bonus: base * (1 + total_percent / 100).
    """
    total = sum(
        m.percent
        for ae in ctx.active_effects
        for m in ae.modifiers
        if m.type == "damage_amplify" and m.target == target
        if isinstance(m.percent, int)
    )
    if total <= 0:
        return base
    return int(base * (1 + total / 100))


def _apply_incoming_modifiers(base: int, target: Literal["player", "enemy"], ctx: CombatContext) -> int:
    """Apply damage_reduction and damage_vulnerability modifiers to incoming damage for target.

    Reductions and vulnerabilities are summed independently, then combined:
        factor = max(0.0, 1.0 - (total_reduction / 100) + (total_vulnerability / 100))
    If base > 0 the result is at minimum 1 (no hit is silently absorbed unless base was 0).
    """
    net_reduction = sum(
        m.percent
        for ae in ctx.active_effects
        for m in ae.modifiers
        if m.type == "damage_reduction" and m.target == target
        if isinstance(m.percent, int)
    )
    net_vuln = sum(
        m.percent
        for ae in ctx.active_effects
        for m in ae.modifiers
        if m.type == "damage_vulnerability" and m.target == target
        if isinstance(m.percent, int)
    )
    factor = max(0.0, 1.0 - net_reduction / 100 + net_vuln / 100)
    if base <= 0:
        return 0
    return max(1, int(base * factor))


async def _apply_reflect(
    taken: int,
    target: Literal["player", "enemy"],
    ctx: CombatContext,
    player: "CharacterState",
    tui: UICallbacks,
) -> None:
    """Reflect a portion of damage taken back to the attacker.

    Sums all damage_reflect modifiers active for target and reflects that
    percentage of `taken` damage onto the opposing side.
    """
    total_reflect = sum(
        m.percent
        for ae in ctx.active_effects
        for m in ae.modifiers
        if m.type == "damage_reflect" and m.target == target
        if isinstance(m.percent, int)
    )
    if total_reflect <= 0 or taken <= 0:
        return
    reflected = max(1, int(taken * total_reflect / 100))
    if target == "player":
        # Player has thorns — attacker (enemy) takes the reflected damage.
        hp_key = "hp"
        old_enemy_hp = ctx.enemy_stats.get(hp_key, 0)
        ctx.enemy_stats[hp_key] = max(0, old_enemy_hp - reflected)
        await tui.show_text(f"[yellow]Thorns! {reflected} damage reflected to the enemy.[/yellow]")
    else:
        # Enemy has thorns — attacker (player) takes the reflected damage.
        player.set_stat(name="hp", value=max(0, int(player.stats.get("hp") or 0) - reflected))
        await tui.show_text(f"[yellow]{reflected} damage reflected back at you![/yellow]")


async def _use_skill_in_combat(
    skill_ref: str,
    ctx: CombatContext,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: UICallbacks,
) -> bool:
    """Attempt to activate a skill during combat. Returns True if the skill fired.

    Validates cooldown, resource cost, and activation condition before firing.
    """
    skill = registry.skills.get(skill_ref)
    if skill is None:
        await tui.show_text(f"[red]Error: skill {skill_ref!r} not found in registry.[/red]")
        return False

    spec = skill.spec

    # Turn-scope cooldown check.
    if spec.cooldown is not None and spec.cooldown.scope == "turn":
        last_used = ctx.skill_uses_this_combat.get(skill_ref, 0)
        turns_required = spec.cooldown.turns
        if isinstance(turns_required, str):
            try:
                turns_required = int(turns_required)
            except (ValueError, TypeError):
                turns_required = 0
        if turns_required is None:
            turns_required = 0
        if last_used > 0 and (ctx.turn_number - last_used) < turns_required:
            remaining = turns_required - (ctx.turn_number - last_used)
            await tui.show_text(f"[yellow]{spec.displayName} is on cooldown ({remaining} turn(s) remaining).[/yellow]")
            return False

    # Adventure-scope cooldown check.
    from oscilla.engine.actions import _skill_on_cooldown

    if spec.cooldown is not None and spec.cooldown.scope != "turn":
        if _skill_on_cooldown(player=player, skill_ref=skill_ref):
            await tui.show_text(f"[yellow]{spec.displayName} is on cooldown.[/yellow]")
            return False

    # Resource cost check.
    if spec.cost is not None:
        current = player.stats.get(spec.cost.stat, 0)
        if not isinstance(current, int) or isinstance(current, bool):
            await tui.show_text(f"[red]Error: resource stat {spec.cost.stat!r} is not numeric.[/red]")
            return False
        if current < spec.cost.amount:
            await tui.show_text(
                f"[red]Not enough {spec.cost.stat} to use {spec.displayName} "
                f"(need {spec.cost.amount}, have {current}).[/red]"
            )
            return False

    # Activation condition check.
    from oscilla.engine.conditions import evaluate

    if not evaluate(condition=spec.requires, player=player, registry=registry):
        await tui.show_text(f"[red]You cannot use {spec.displayName} right now.[/red]")
        return False

    # All checks passed — deduct resource cost.
    if spec.cost is not None:
        old = int(player.stats.get(spec.cost.stat) or 0)
        player.set_stat(name=spec.cost.stat, value=old - spec.cost.amount)

    # Record use for cooldown tracking.
    if spec.cooldown is not None:
        if spec.cooldown.scope == "turn":
            ctx.skill_uses_this_combat[skill_ref] = ctx.turn_number
        else:  # adventure-scope — persist via tick/real expiry
            from oscilla.engine.actions import _set_skill_cooldown

            _set_skill_cooldown(player=player, skill_ref=skill_ref, cooldown=spec.cooldown)

    # Dispatch immediate use_effects (including any apply_buff effects).
    await tui.show_text(f"You use [bold]{spec.displayName}[/bold]!")
    for eff in spec.use_effects:
        await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)

    return True


async def _enemy_skill_phase(
    ctx: CombatContext,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: UICallbacks,
    spec: "CombatSystemSpec | None" = None,
) -> None:
    """Check and fire any enemy skills whose use_every_n_turns threshold is met.

    Called at the end of each round, after the enemy's basic attack.
    Skills with use_every_n_turns=0 are never auto-fired.
    ``spec`` is accepted for future AI hook compatibility but not used yet.
    """
    enemy = registry.enemies.require(ctx.enemy_ref, "Enemy")
    for skill_entry in enemy.spec.skills:
        n = skill_entry.use_every_n_turns
        if n == 0:
            continue
        if ctx.turn_number % n == 0:
            skill = registry.skills.get(skill_entry.skill_ref)
            if skill is None:
                logger.warning("Enemy skill ref %r not found in registry — skipping.", skill_entry.skill_ref)
                continue
            skill_spec = skill.spec

            # Resource check for enemy.
            if skill_spec.cost is not None:
                available = ctx.enemy_resources.get(skill_spec.cost.stat, 0)
                if available < skill_spec.cost.amount:
                    continue  # Not enough resource; skip silently.
                ctx.enemy_resources[skill_spec.cost.stat] = available - skill_spec.cost.amount

            await tui.show_text(
                f"[bold]{enemy.spec.displayName}[/bold] uses [italic]{skill_spec.displayName}[/italic]!"
            )
            for eff in skill_spec.use_effects:
                await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)


# Alias kept for backwards compatibility — callers should prefer enemy_action_phase.
enemy_action_phase = _enemy_skill_phase


def merge_overrides(base: "CombatSystemSpec", overrides: "CombatStepOverrides | None") -> "CombatSystemSpec":
    """Return a new CombatSystemSpec with any non-None fields from ``overrides`` applied.

    ``None`` overrides pass through unchanged. Only override fields that are explicitly
    set (not ``None``) replace the corresponding base field.
    """
    if overrides is None:
        return base
    # Build a dict of only the non-None override fields.
    update_data = {k: v for k, v in overrides.model_dump(exclude_none=True).items() if v is not None}
    if not update_data:
        return base
    return base.model_copy(update=update_data)


def resolve_turn_order(
    spec: "CombatSystemSpec",
    formula_ctx: CombatFormulaContext,
) -> Literal["player_first", "enemy_first", "simultaneous"]:
    """Determine combat turn order for this round based on the CombatSystemSpec.

    Handles ``"player_first"``, ``"enemy_first"``, and ``"simultaneous"`` directly.
    For ``"initiative"`` mode, renders both formula fields; higher result returns
    ``"player_first"`` or ``"enemy_first"``; ties resolved by ``spec.initiative_tie``.
    """
    mode = spec.turn_order
    if mode == "player_first":
        return "player_first"
    if mode == "enemy_first":
        return "enemy_first"
    if mode == "simultaneous":
        return "simultaneous"

    # initiative mode
    player_formula = spec.player_initiative_formula or "{{ 0 }}"
    enemy_formula = spec.enemy_initiative_formula or "{{ 0 }}"
    try:
        player_init = render_formula(formula=player_formula, ctx=formula_ctx)
        enemy_init = render_formula(formula=enemy_formula, ctx=formula_ctx)
    except FormulaRenderError:
        logger.exception("Initiative formula render failed; defaulting to player_first.")
        return "player_first"

    logger.debug("Initiative: player=%d, enemy=%d", player_init, enemy_init)

    if player_init > enemy_init:
        return "player_first"
    if enemy_init > player_init:
        return "enemy_first"
    # Tie
    tie_rule = spec.initiative_tie or "player_first"
    if tie_rule == "enemy_first":
        return "enemy_first"
    if tie_rule == "simultaneous":
        return "simultaneous"
    return "player_first"


def resolve_target(
    entry: "DamageFormulaEntry",
    ctx: CombatContext,
    player: "CharacterState",
) -> Dict[str, int]:
    """Return the stat dict to mutate based on ``entry.target``.

    - ``"player"`` → ``player.stats`` (cast to Dict[str, int])
    - ``"enemy"``  → ``ctx.enemy_stats``
    - ``"combat"`` → ``ctx.combat_stats``
    - ``None`` with ``target_stat`` set → ``ctx.enemy_stats`` (legacy default)
    """
    target = entry.target
    if target == "player":
        return {k: v for k, v in player.stats.items() if isinstance(v, int)}
    if target == "combat":
        return ctx.combat_stats
    # "enemy" or None with a target_stat
    return ctx.enemy_stats


async def apply_damage_formula(
    entry: "DamageFormulaEntry",
    formula_ctx: CombatFormulaContext,
    ctx: CombatContext,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: UICallbacks,
) -> None:
    """Render a DamageFormulaEntry formula and apply the result to the correct stat namespace.

    Evaluates ``threshold_effects`` bands and runs matched effects, then logs
    the display label when set.
    """
    from oscilla.engine.conditions import evaluate

    try:
        value = render_formula(formula=entry.formula, ctx=formula_ctx)
    except FormulaRenderError:
        logger.exception("Damage formula %r failed to render — skipping.", entry.formula)
        return

    # Write the value to the appropriate stat dict.
    if entry.target_stat is not None:
        target_dict = resolve_target(entry=entry, ctx=ctx, player=player)
        if entry.target == "player":
            # Player stats must go through set_stat to trigger derived stat recalculation.
            old_val = int(player.stats.get(entry.target_stat) or 0)
            new_val = old_val + value
            player.set_stat(name=entry.target_stat, value=new_val)
        else:
            target_dict[entry.target_stat] = target_dict.get(entry.target_stat, 0) + value

    # Evaluate threshold_effects bands in order; fire the first matching band.
    for band in entry.threshold_effects:
        lo_ok = band.min is None or value >= band.min
        hi_ok = band.max is None or value <= band.max
        if lo_ok and hi_ok:
            for eff in band.effects:
                await run_effect(
                    effect=eff,
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=ctx,
                )
            break  # Only first matching band fires.

    if entry.display:
        try:
            display_text = render_formula(formula=entry.display, ctx=formula_ctx)
            await tui.show_text(str(display_text))
        except FormulaRenderError:
            logger.warning("Damage formula display %r failed to render — skipping display.", entry.display)

    # Evaluate defeat conditions after each formula application.
    _ = evaluate  # used in run_combat defeat check; suppress F841


async def player_action_phase(
    spec: "CombatSystemSpec",
    ctx: CombatContext,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: UICallbacks,
    formula_ctx: CombatFormulaContext,
    run_outcome_branch: Callable[[OutcomeBranch], Awaitable[AdventureOutcome]],
    on_flee: "OutcomeBranch",
    combat_skills: List[str],
) -> AdventureOutcome | None:
    """Execute the player action phase for one combat round.

    Returns ``AdventureOutcome.FLED`` if the player chooses to flee,
    otherwise returns ``None`` to continue the round.

    Dispatch based on ``spec.player_turn_mode``:
    - ``"auto"``: runs each DamageFormulaEntry in ``spec.player_damage_formulas``.
    - ``"choice"``: presents a menu of system skills, player-owned combat skills, and Flee.
    """
    from oscilla.engine.conditions import evaluate

    if spec.player_turn_mode == "auto":
        for entry in spec.player_damage_formulas:
            await apply_damage_formula(
                entry=entry,
                formula_ctx=formula_ctx,
                ctx=ctx,
                player=player,
                registry=registry,
                tui=tui,
            )
        return None

    # "choice" mode — build the action menu.
    menu_options: List[str] = []
    action_map: List[str] = []  # parallel list of skill/system refs

    # System skills (filtered by condition).
    for sys_skill in spec.system_skills:
        if sys_skill.condition is None or evaluate(
            condition=sys_skill.condition,
            player=player,
            registry=registry,
            enemy_stats=ctx.enemy_stats,
            combat_stats=ctx.combat_stats,
        ):
            skill_m = registry.skills.get(sys_skill.skill)
            label = skill_m.spec.displayName if skill_m else sys_skill.skill
            menu_options.append(f"[System] {label}")
            action_map.append(f"system:{sys_skill.skill}")

    # Player-owned combat skills.
    for skill_ref in combat_skills:
        skill_m = registry.skills.get(skill_ref)
        if skill_m is None:
            continue
        s_spec = skill_m.spec
        # Include skill if it's usable in any of the system's skill_contexts.
        if any(ctx_name in s_spec.contexts for ctx_name in (spec.skill_contexts or ["combat"])):
            menu_options.append(f"Skill: {s_spec.displayName}")
            action_map.append(f"skill:{skill_ref}")

    menu_options.append("Flee")
    flee_index = len(menu_options)  # 1-based

    action = await tui.show_menu("Your move:", menu_options)

    if action == flee_index:
        await run_outcome_branch(on_flee)
        return AdventureOutcome.FLED

    chosen = action_map[action - 1]
    if chosen.startswith("system:"):
        skill_ref = chosen.removeprefix("system:")
        await _use_skill_in_combat(skill_ref=skill_ref, ctx=ctx, player=player, registry=registry, tui=tui)
    elif chosen.startswith("skill:"):
        skill_ref = chosen.removeprefix("skill:")
        await _use_skill_in_combat(skill_ref=skill_ref, ctx=ctx, player=player, registry=registry, tui=tui)

    return None


async def run_combat(
    step: CombatStep,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: UICallbacks,
    run_outcome_branch: Callable[[OutcomeBranch], Awaitable[AdventureOutcome]],
    on_round_complete: Callable[[], Awaitable[None]] | None = None,
) -> AdventureOutcome:
    """Execute the turn-based combat loop driven by a CombatSystem manifest.

    When a CombatSystem can be resolved the new formula-based path is used.
    CombatContext is constructed here and passed to all sub-functions — it is
    never serialized. ``enemy_stats`` and ``combat_stats`` are mirrored to
    step_state each round for persistence.

    on_round_complete is called after all stat changes for the round are committed.
    This is the persistence hook used by GameSession.
    """

    enemy = registry.enemies.require(step.enemy, "Enemy")

    # Resolve the CombatSystem manifest (may be None if content lacks one).
    combat_system_manifest = registry.resolve_combat_system(name=step.combat_system)
    combat_spec = (
        merge_overrides(
            base=combat_system_manifest.spec,
            overrides=step.combat_overrides,
        )
        if combat_system_manifest is not None
        else None
    )

    # Determine whether this is a fresh combat or a resume.
    is_resume = bool(
        player.active_adventure
        and "enemy_stats" in player.active_adventure.step_state
        and player.active_adventure.step_state["enemy_stats"]
    )

    # Initialize enemy_stats.
    if is_resume and player.active_adventure:
        raw = player.active_adventure.step_state["enemy_stats"]
        enemy_stats: Dict[str, int] = {k: int(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
    else:
        enemy_stats = dict(enemy.spec.stats)
        if player.active_adventure:
            player.active_adventure.step_state["enemy_stats"] = dict(enemy_stats)

    # Initialize combat_stats from step_state (resume) or spec defaults (new).
    if is_resume and player.active_adventure and "combat_stats" in player.active_adventure.step_state:
        raw_cs = player.active_adventure.step_state["combat_stats"]
        combat_stats_init: Dict[str, int] = {k: int(v) for k, v in raw_cs.items()} if isinstance(raw_cs, dict) else {}
    elif combat_spec is not None:
        combat_stats_init = {entry.name: entry.default for entry in combat_spec.combat_stats}
    else:
        combat_stats_init = {}

    ctx = CombatContext(
        enemy_stats=enemy_stats,
        enemy_ref=step.enemy,
        combat_stats=combat_stats_init,
        enemy_resources=dict(enemy.spec.skill_resources),
    )

    # Fire on_combat_start effects for new (non-resume) combats only.
    if not is_resume and combat_spec is not None:
        for eff in combat_spec.on_combat_start:
            await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)

    # Sweep and re-inject persistent buffs from CharacterState.
    now_ts = int(time.time())
    player.sweep_expired_buffs(
        now_tick=player.internal_ticks,
        now_game_tick=player.game_ticks,
        now_ts=now_ts,
    )
    # Track all buff refs injected from StoredBuff; needed for correct writeback even when
    # a buff expires during combat and is removed from ctx.active_effects before the loop ends.
    injected_persistent_refs: Set[str] = set()
    for stored in player.active_buffs:
        buff_manifest = registry.buffs.get(stored.buff_ref)
        if buff_manifest is None:
            logger.warning(
                "Stored buff %r not found in registry at combat start — skipping.",
                stored.buff_ref,
            )
            continue
        spec = buff_manifest.spec
        resolved_vars: Dict[str, int] = {**spec.variables, **stored.variables}
        resolved_modifiers = [
            mod.model_copy(
                update={"percent": resolved_vars.get(mod.percent, 0) if isinstance(mod.percent, str) else mod.percent}
            )
            for mod in spec.modifiers
        ]
        ae = ActiveCombatEffect(
            source_skill=buff_manifest.metadata.name,
            target="player",
            remaining_turns=stored.remaining_turns,
            per_turn_effects=list(spec.per_turn_effects),
            modifiers=resolved_modifiers,
            label=stored.buff_ref,
            exclusion_group=spec.exclusion_group or "",
            priority=resolved_vars.get(spec.priority, 0) if isinstance(spec.priority, str) else int(spec.priority),
            exclusion_mode=spec.exclusion_mode,
            is_persistent=True,
            variables=dict(resolved_vars),
        )
        ctx.active_effects.append(ae)
        injected_persistent_refs.add(stored.buff_ref)

    # Apply combat-entry buffs granted by equipped and held items.
    equipped_refs: Set[str] = {
        inst.item_ref for inst in player.instances if inst.instance_id in player.equipment.values()
    }
    for item_ref in equipped_refs:
        item_m = registry.items.get(item_ref)
        if item_m is not None:
            for grant in item_m.spec.grants_buffs_equipped:
                await run_effect(
                    effect=ApplyBuffEffect(
                        type="apply_buff",
                        buff_ref=grant.buff_ref,
                        target="player",
                        variables=grant.variables,
                    ),
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=ctx,
                )
    held_refs: Set[str] = {inst.item_ref for inst in player.instances} | set(player.stacks.keys())
    for item_ref in held_refs:
        item_m = registry.items.get(item_ref)
        if item_m is not None:
            for grant in item_m.spec.grants_buffs_held:
                await run_effect(
                    effect=ApplyBuffEffect(
                        type="apply_buff",
                        buff_ref=grant.buff_ref,
                        target="player",
                        variables=grant.variables,
                    ),
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=ctx,
                )

    # Determine which skills the player can use in combat.
    combat_skills: List[str] = [
        skill_ref
        for skill_ref in player.available_skills(registry=registry)
        if (s := registry.skills.get(skill_ref)) is not None and "combat" in s.spec.contexts
    ]

    outcome: AdventureOutcome = AdventureOutcome.COMPLETED  # default; set by break statements

    while True:
        # Tick periodic effects at the top of each round.
        await _tick_active_effects(ctx=ctx, player=player, registry=registry, tui=tui)

        await tui.show_combat_round(
            player_hp=int(player.stats.get("hp") or 0),
            enemy_hp=ctx.enemy_stats.get("hp", 0),
            player_name=player.name,
            enemy_name=enemy.spec.displayName,
        )

        # Build formula context (fresh each round for accurate turn_number / stats).
        formula_ctx = CombatFormulaContext(
            player={k: v for k, v in player.stats.items() if isinstance(v, int)},
            enemy_stats=dict(ctx.enemy_stats),
            combat_stats=dict(ctx.combat_stats),
            turn_number=ctx.turn_number,
        )

        # Determine turn order for this round.
        if combat_spec is not None:
            turn_order = resolve_turn_order(spec=combat_spec, formula_ctx=formula_ctx)
        else:
            turn_order = "player_first"

        # ---------------------------------------------------------------
        # Player action phase
        # ---------------------------------------------------------------
        if turn_order != "enemy_first":
            if combat_spec is not None:
                fled = await player_action_phase(
                    spec=combat_spec,
                    ctx=ctx,
                    player=player,
                    registry=registry,
                    tui=tui,
                    formula_ctx=formula_ctx,
                    run_outcome_branch=run_outcome_branch,
                    on_flee=step.on_flee,
                    combat_skills=combat_skills,
                )
                if fled == AdventureOutcome.FLED:
                    outcome = AdventureOutcome.FLED
                    break
            else:
                # Legacy: present a simple attack/flee menu.
                menu_options: List[str] = ["Attack"]
                skill_indices: List[str] = []
                for skill_ref in combat_skills:
                    skill = registry.skills.get(skill_ref)
                    if skill is not None:
                        menu_options.append(f"Skill: {skill.spec.displayName}")
                        skill_indices.append(skill_ref)
                menu_options.append("Flee")
                flee_index = len(menu_options)
                action = await tui.show_menu("Your move:", menu_options)
                if action == flee_index:
                    await run_outcome_branch(step.on_flee)
                    outcome = AdventureOutcome.FLED
                    break
                if action == 1:
                    await tui.show_text("You attack!")
                elif 2 <= action < flee_index:
                    skill_ref = skill_indices[action - 2]
                    await _use_skill_in_combat(skill_ref=skill_ref, ctx=ctx, player=player, registry=registry, tui=tui)

        # ---------------------------------------------------------------
        # Defeat check (sequential modes only, after player acts)
        # ---------------------------------------------------------------
        player_defeated = bool((player.stats.get("hp") or 0) <= 0)
        enemy_defeated = _check_enemy_defeat(ctx=ctx, player=player, combat_spec=combat_spec)

        if turn_order != "simultaneous":
            if enemy_defeated:
                if player.active_adventure:
                    player.active_adventure.step_state["enemy_stats"] = dict(ctx.enemy_stats)
                    player.active_adventure.step_state["combat_stats"] = dict(ctx.combat_stats)
                ctx.turn_number += 1
                if on_round_complete is not None:
                    await on_round_complete()
                await _handle_victory(
                    ctx=ctx,
                    step=step,
                    enemy=enemy,
                    player=player,
                    registry=registry,
                    tui=tui,
                    run_outcome_branch=run_outcome_branch,
                    combat_spec=combat_spec,
                )
                outcome = AdventureOutcome.COMPLETED
                break
            if player_defeated:
                if player.active_adventure:
                    player.active_adventure.step_state["enemy_stats"] = dict(ctx.enemy_stats)
                    player.active_adventure.step_state["combat_stats"] = dict(ctx.combat_stats)
                ctx.turn_number += 1
                if on_round_complete is not None:
                    await on_round_complete()
                await run_outcome_branch(step.on_defeat)
                outcome = AdventureOutcome.DEFEATED
                break
        # ---------------------------------------------------------------
        if not enemy_defeated or turn_order == "simultaneous":
            if combat_spec is not None:
                for entry in combat_spec.enemy_damage_formulas:
                    await apply_damage_formula(
                        entry=entry,
                        formula_ctx=formula_ctx,
                        ctx=ctx,
                        player=player,
                        registry=registry,
                        tui=tui,
                    )
            else:
                # No-op enemy attack when no spec (no hardcoded stats on enemy anymore).
                pass

            await _enemy_skill_phase(ctx=ctx, player=player, registry=registry, tui=tui, spec=combat_spec)

        # ---------------------------------------------------------------
        # Defeat check (sequential, after enemy acts)
        # ---------------------------------------------------------------
        if turn_order != "simultaneous":
            player_defeated = bool((player.stats.get("hp") or 0) <= 0)
            enemy_defeated = _check_enemy_defeat(ctx=ctx, player=player, combat_spec=combat_spec)
            if enemy_defeated:
                if player.active_adventure:
                    player.active_adventure.step_state["enemy_stats"] = dict(ctx.enemy_stats)
                    player.active_adventure.step_state["combat_stats"] = dict(ctx.combat_stats)
                ctx.turn_number += 1
                if on_round_complete is not None:
                    await on_round_complete()
                await _handle_victory(
                    ctx=ctx,
                    step=step,
                    enemy=enemy,
                    player=player,
                    registry=registry,
                    tui=tui,
                    run_outcome_branch=run_outcome_branch,
                    combat_spec=combat_spec,
                )
                outcome = AdventureOutcome.COMPLETED
                break
            if player_defeated:
                if player.active_adventure:
                    player.active_adventure.step_state["enemy_stats"] = dict(ctx.enemy_stats)
                    player.active_adventure.step_state["combat_stats"] = dict(ctx.combat_stats)
                ctx.turn_number += 1
                if on_round_complete is not None:
                    await on_round_complete()
                await run_outcome_branch(step.on_defeat)
                outcome = AdventureOutcome.DEFEATED
                break

        # ---------------------------------------------------------------
        # Resolution formulas phase (always for simultaneous; only when
        # no mid-round defeat in sequential modes — handled by break above)
        # ---------------------------------------------------------------
        if combat_spec is not None:
            for entry in combat_spec.resolution_formulas:
                await apply_damage_formula(
                    entry=entry,
                    formula_ctx=formula_ctx,
                    ctx=ctx,
                    player=player,
                    registry=registry,
                    tui=tui,
                )

        # ---------------------------------------------------------------
        # On-round-end effects and final defeat check
        # ---------------------------------------------------------------
        if combat_spec is not None:
            for eff in combat_spec.on_round_end:
                await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)

        # Persist state in step_state for save/restore.
        if player.active_adventure:
            player.active_adventure.step_state["enemy_stats"] = dict(ctx.enemy_stats)
            player.active_adventure.step_state["combat_stats"] = dict(ctx.combat_stats)

        ctx.turn_number += 1

        # Checkpoint after all stat changes for this round are committed.
        if on_round_complete is not None:
            await on_round_complete()

        # Final defeat check after on_round_end.
        player_defeated = bool((player.stats.get("hp") or 0) <= 0)
        enemy_defeated = _check_enemy_defeat(ctx=ctx, player=player, combat_spec=combat_spec)

        if turn_order == "simultaneous" and enemy_defeated and player_defeated:
            # Mutual defeat — resolve per spec.
            sim_result = combat_spec.simultaneous_defeat_result if combat_spec else "player_loses"
            if sim_result == "player_wins":
                await _handle_victory(
                    ctx=ctx,
                    step=step,
                    enemy=enemy,
                    player=player,
                    registry=registry,
                    tui=tui,
                    run_outcome_branch=run_outcome_branch,
                    combat_spec=combat_spec,
                )
                outcome = AdventureOutcome.COMPLETED
            else:
                await run_outcome_branch(step.on_defeat)
                outcome = AdventureOutcome.DEFEATED
            break

        if enemy_defeated:
            await _handle_victory(
                ctx=ctx,
                step=step,
                enemy=enemy,
                player=player,
                registry=registry,
                tui=tui,
                run_outcome_branch=run_outcome_branch,
                combat_spec=combat_spec,
            )
            outcome = AdventureOutcome.COMPLETED
            break

        if player_defeated:
            await run_outcome_branch(step.on_defeat)
            outcome = AdventureOutcome.DEFEATED
            break

        if turn_order == "enemy_first":
            # Player has not acted yet this round.
            if combat_spec is not None:
                fled = await player_action_phase(
                    spec=combat_spec,
                    ctx=ctx,
                    player=player,
                    registry=registry,
                    tui=tui,
                    formula_ctx=formula_ctx,
                    run_outcome_branch=run_outcome_branch,
                    on_flee=step.on_flee,
                    combat_skills=combat_skills,
                )
                if fled == AdventureOutcome.FLED:
                    outcome = AdventureOutcome.FLED
                    break
            else:
                menu_opts: List[str] = ["Attack", "Flee"]
                a = await tui.show_menu("Your move:", menu_opts)
                if a == 2:
                    await run_outcome_branch(step.on_flee)
                    outcome = AdventureOutcome.FLED
                    break

            # Defeat check after delayed player phase.
            enemy_defeated = _check_enemy_defeat(ctx=ctx, player=player, combat_spec=combat_spec)
            if enemy_defeated:
                await _handle_victory(
                    ctx=ctx,
                    step=step,
                    enemy=enemy,
                    player=player,
                    registry=registry,
                    tui=tui,
                    run_outcome_branch=run_outcome_branch,
                    combat_spec=combat_spec,
                )
                outcome = AdventureOutcome.COMPLETED
                break

    # Fire on_combat_end then win/defeat lifecycle hooks.
    if combat_spec is not None:
        for eff in combat_spec.on_combat_end:
            await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)
        if outcome == AdventureOutcome.COMPLETED:
            for eff in combat_spec.on_combat_victory:
                await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)
        elif outcome == AdventureOutcome.DEFEATED:
            for eff in combat_spec.on_combat_defeat:
                await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)

    # Write back persistent buffs to CharacterState after combat.
    # Buffs that still have remaining turns are updated; exhausted buffs are removed.
    # Use injected_persistent_refs (not just currently active) so buffs that expired
    # during combat (ticked to 0 and already popped) are also cleared from active_buffs.
    player.active_buffs = [sb for sb in player.active_buffs if sb.buff_ref not in injected_persistent_refs]
    for ae in ctx.active_effects:
        if ae.is_persistent and ae.remaining_turns > 0:
            player.active_buffs.append(
                StoredBuff(
                    buff_ref=ae.label,
                    remaining_turns=ae.remaining_turns,
                    variables=dict(ae.variables),
                )
            )

    return outcome


def _check_enemy_defeat(
    ctx: CombatContext,
    player: "CharacterState",
    combat_spec: "CombatSystemSpec | None",
) -> bool:
    """Check whether the enemy defeat condition is met.

    When a CombatSystem spec is available, evaluates the configured
    ``enemy_defeat_condition``. Falls back to ``enemy_stats.get("hp", 0) <= 0``.
    """
    from oscilla.engine.conditions import evaluate

    if combat_spec is not None and combat_spec.enemy_defeat_condition is not None:
        return evaluate(
            condition=combat_spec.enemy_defeat_condition,
            player=player,
            registry=None,
            enemy_stats=ctx.enemy_stats,
            combat_stats=ctx.combat_stats,
        )
    # Default: hp-based defeat.
    return ctx.enemy_stats.get("hp", 0) <= 0


async def _handle_victory(
    ctx: CombatContext,
    step: CombatStep,
    enemy: "Any",
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: UICallbacks,
    run_outcome_branch: Callable[[OutcomeBranch], Awaitable[AdventureOutcome]],
    combat_spec: "CombatSystemSpec | None",
) -> None:
    """Run victory sequence: record defeat, on_defeat_effects, loot, then on_win branch."""
    player.statistics.record_enemy_defeated(step.enemy)
    # Run enemy on_defeat_effects.
    for eff in enemy.spec.on_defeat_effects:
        await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=ctx)
    # Automatically apply the enemy's own loot groups before the on_win branch.
    if enemy.spec.loot:
        loot_effect = ItemDropEffect(type="item_drop", groups=enemy.spec.loot)
        await run_effect(effect=loot_effect, player=player, registry=registry, tui=tui)
    await run_outcome_branch(step.on_win)

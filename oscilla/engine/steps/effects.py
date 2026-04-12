"""Effect dispatcher — applies mechanical outcomes to player state and notifies the TUI."""

from __future__ import annotations

import random
from collections import Counter
from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict, List, Set

from oscilla.engine.character import _INT64_MAX, _INT64_MIN, PrestigeCarryForward, cascade_unequip_invalid
from oscilla.engine.combat_context import ActiveCombatEffect, CombatContext
from oscilla.engine.models.adventure import (
    AdjustGameTicksEffect,
    ApplyBuffEffect,
    ArchetypeAddEffect,
    ArchetypeRemoveEffect,
    DispelEffect,
    Effect,
    EmitTriggerEffect,
    EndAdventureEffect,
    HealEffect,
    ItemDropEffect,
    MilestoneGrantEffect,
    PrestigeEffect,
    QuestActivateEffect,
    QuestFailEffect,
    SetNameEffect,
    SetPronounsEffect,
    SkillGrantEffect,
    SkillRevokeEffect,
    StatChangeEffect,
    StatSetEffect,
    UseItemEffect,
)
from oscilla.engine.signals import _EndSignal

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.models.loot_table import LootGroup
    from oscilla.engine.pipeline import UICallbacks
    from oscilla.engine.registry import ContentRegistry
    from oscilla.engine.templates import ExpressionContext

logger = getLogger(__name__)


async def _fire_threshold_triggers(
    stat_name: str,
    old_value: int | None,
    new_value: int | None,
    player: "CharacterState",
    registry: "ContentRegistry",
) -> None:
    """Enqueue on_stat_threshold triggers for an upward stat transition.

    Handles two firing modes per entry:
      - "each"    — every threshold crossed in one mutation enqueues separately
                    (sorted ascending so lower thresholds fire first)
      - "highest" — only the single highest crossed threshold enqueues;
                    lower-threshold entries are suppressed

    Both groups operate independently: all "each" entries fire first (ascending),
    then the highest-threshold "highest" entry fires (if any).
    Downward crossings are not supported — only upward crossings fire.
    """
    from oscilla.engine.models.game import StatThresholdTrigger

    game = registry.game
    if game is None:
        return

    thresholds = game.spec.triggers.on_stat_threshold
    if not thresholds:
        return

    if old_value is None or new_value is None:
        return

    # Collect all threshold entries for this stat that were crossed upward.
    crossed: List[StatThresholdTrigger] = [
        t for t in thresholds if t.stat == stat_name and old_value < t.threshold <= new_value
    ]

    max_depth = game.spec.triggers.max_trigger_queue_depth

    # --- fire_mode: each --- fire every crossed entry in ascending threshold order.
    each_entries = sorted(
        (t for t in crossed if t.fire_mode == "each"),
        key=lambda t: t.threshold,
    )
    for threshold_entry in each_entries:
        if threshold_entry.name in registry.trigger_index:
            player.enqueue_trigger(threshold_entry.name, max_depth=max_depth)

    # --- fire_mode: highest --- fire only the single highest crossed entry.
    highest_entries = [t for t in crossed if t.fire_mode == "highest"]
    if highest_entries:
        top = max(highest_entries, key=lambda t: t.threshold)
        if top.name in registry.trigger_index:
            player.enqueue_trigger(top.name, max_depth=max_depth)


async def _recompute_derived_stats(
    player: "CharacterState",
    registry: "ContentRegistry",
    engine: "Any",
    tui: "UICallbacks",
) -> None:
    """Re-evaluate all derived stats and fire on_stat_threshold triggers for any that changed.

    Called after every stat_change or stat_set that modifies a stored stat.
    Derived stats are never written directly — their computed values exist only
    in the shadow dict. The shadow dict is compared to the new computed value;
    when they differ, on_stat_threshold entries for that stat are evaluated.

    Multi-cross behavior: if a derived stat's value jumps past multiple threshold
    values in a single recomputation, all crossed thresholds fire in ascending order.
    """
    from oscilla.engine.templates import ExpressionContext, GameContext, PlayerContext

    char_config = registry.character_config
    if char_config is None:
        return

    derived_stats = getattr(registry, "derived_eval_order", [])
    if not derived_stats:
        return

    game = registry.game
    game_spec = game.spec if game is not None else None
    hemisphere = game_spec.season_hemisphere if game_spec is not None else "northern"
    timezone = game_spec.timezone if game_spec is not None else None

    # Precompute effective stats once if any derived stat needs them.
    effective: Dict[str, int | bool | None] | None = None
    if any(s.stat_context == "effective" for s in derived_stats):
        effective = player.effective_stats(registry=registry)

    # working_stats accumulates stored stats + already-evaluated derived values
    # so derived-from-derived chains work correctly.
    working_stats: Dict[str, int | bool | None] = dict(player.stats)

    for stat_def in derived_stats:
        assert stat_def.derived is not None
        template_id = f"__derived_{stat_def.name}"
        try:
            base_stats = effective if stat_def.stat_context == "effective" and effective is not None else working_stats
            # Merge already-computed derived values for cross-derived chaining.
            formula_stats: Dict[str, int | bool | None] = {
                **base_stats,
                **{k: v for k, v in working_stats.items() if k not in base_stats},
            }
            # Build a temporary PlayerContext with the merged formula stats.
            from oscilla.engine.character import _INT64_MAX, _INT64_MIN

            render_player = PlayerContext.from_character(player)
            # Override stats with the merged formula view
            render_player = type(render_player)(
                name=render_player.name,
                prestige_count=render_player.prestige_count,
                stats=formula_stats,
                milestones=render_player.milestones,
                pronouns=render_player.pronouns,
            )
            ctx = ExpressionContext(
                player=render_player,
                game=GameContext(season_hemisphere=hemisphere, timezone=timezone),
            )
            result_str = engine.render(template_id=template_id, ctx=ctx).strip()
            new_value: int | None = int(result_str) if result_str else None
        except Exception:
            logger.exception(
                "Failed to evaluate derived stat %r formula at runtime — skipping.",
                stat_def.name,
            )
            continue

        # Apply bounds clamping to derived values, same as stored stats.
        if new_value is not None and stat_def.bounds is not None:
            from oscilla.engine.character import _INT64_MAX, _INT64_MIN

            lo = stat_def.bounds.min if stat_def.bounds.min is not None else _INT64_MIN
            hi = stat_def.bounds.max if stat_def.bounds.max is not None else _INT64_MAX
            new_value = max(lo, min(hi, new_value))

        old_value = player._derived_shadows.get(stat_def.name)
        player._derived_shadows[stat_def.name] = new_value
        # Make this derived value available for downstream derived stats.
        working_stats[stat_def.name] = new_value

        if old_value == new_value:
            continue

        # Fire on_stat_threshold triggers for this derived stat.
        await _fire_threshold_triggers(
            stat_name=stat_def.name,
            old_value=old_value if isinstance(old_value, int) else None,
            new_value=new_value if isinstance(new_value, int) else None,
            player=player,
            registry=registry,
        )


def _resolve_stat_bounds(stat: str, registry: "ContentRegistry") -> tuple[int, int]:
    """Return the effective (min, max) bounds for a named stat.

    Looks up the stat in the registry's CharacterConfig.  If no CharacterConfig
    is loaded, or the stat has no explicit bounds, defaults to INT64_MIN/MAX.
    """
    char_config = registry.character_config
    if char_config is None:
        return _INT64_MIN, _INT64_MAX
    all_stats = char_config.spec.public_stats + char_config.spec.hidden_stats
    for stat_def in all_stats:
        if stat_def.name == stat:
            if stat_def.bounds is None:
                return _INT64_MIN, _INT64_MAX
            lo = stat_def.bounds.min if stat_def.bounds.min is not None else _INT64_MIN
            hi = stat_def.bounds.max if stat_def.bounds.max is not None else _INT64_MAX
            return lo, hi
    return _INT64_MIN, _INT64_MAX


def _resolve_loot_groups(
    groups: "List[LootGroup]",
    player: "CharacterState",
    registry: "ContentRegistry",
    ctx: "ExpressionContext",
) -> "List[tuple[str, int]]":
    """Resolve a list of LootGroups into (item_ref, amount) pairs.

    Each group is processed independently:
    - group.requires is evaluated; the group is skipped if it returns False.
    - Each entry's requires is evaluated; entries not passing are excluded from the pool.
    - If the pool is empty after filtering, the group is silently skipped.
    - group.count (template-capable) is resolved and clamped to max(0, value).
    - method="weighted" draws with replacement using entry weights.
    - method="unique" draws without replacement via random.sample; count is clamped
      to min(count, len(pool)) since random.sample cannot exceed population size.
    - entry.amount (template-capable) is resolved per chosen entry and clamped to max(0).

    Returns a flat list of (item_ref, amount) tuples, one per drawn entry instance.
    """
    from oscilla.engine.conditions import evaluate

    engine = registry.template_engine
    results: List[tuple[str, int]] = []

    for group in groups:
        if group.requires is not None and not evaluate(group.requires, player, registry):
            continue
        pool = [e for e in group.entries if e.requires is None or evaluate(e.requires, player, registry)]
        if not pool:
            continue

        # Resolve count — template string or plain int.
        if isinstance(group.count, str) and engine is not None:
            template_id = f"__lootgroup_count_{id(group)}"
            count = max(0, engine.render_int(template_id, ctx))
        else:
            count = max(0, int(group.count))

        if count == 0:
            continue

        if group.method == "unique":
            chosen = random.sample(pool, k=min(count, len(pool)))
        else:
            weights = [e.weight for e in pool]
            chosen = random.choices(pool, weights=weights, k=count)

        for entry in chosen:
            if isinstance(entry.amount, str) and engine is not None:
                template_id = f"__lootentry_amount_{id(entry)}"
                amount = max(0, engine.render_int(template_id, ctx))
            else:
                amount = max(0, int(entry.amount))
            results.append((entry.item, amount))

    return results


async def run_effect(
    effect: Effect,
    player: "CharacterState",
    registry: "ContentRegistry",
    tui: "UICallbacks",
    combat: "CombatContext | None" = None,
    ctx: "ExpressionContext | None" = None,
) -> None:
    """Dispatch a single effect to its handler.

    combat must be provided for any effect with target="enemy". When absent and
    target="enemy" is requested, a warning is logged and the effect is skipped
    rather than crashing — this can occur if a skill with combat-only effects is
    somehow invoked outside combat.
    """
    # Resolve any template strings in numeric fields before dispatch.
    if registry.template_engine is not None:
        from oscilla.engine.templates import ExpressionContext, GameContext, PlayerContext

        if ctx is None:
            game_spec = registry.game.spec if registry.game is not None else None
            hemisphere = game_spec.season_hemisphere if game_spec is not None else "northern"
            timezone = game_spec.timezone if game_spec is not None else None
            ctx = ExpressionContext(
                player=PlayerContext.from_character(player),
                game=GameContext(season_hemisphere=hemisphere, timezone=timezone),
            )
        engine = registry.template_engine

        if isinstance(effect, StatChangeEffect) and isinstance(effect.amount, str):
            template_id = f"__effect_statchange_{id(effect)}"
            resolved_amount = engine.render_int(template_id, ctx)
            effect = StatChangeEffect(
                type="stat_change",
                stat=effect.stat,
                amount=resolved_amount,
                target=effect.target,
            )

    match effect:
        case ItemDropEffect():
            # Resolve groups: either inline or via loot_ref.
            groups: List[LootGroup]
            if effect.groups is not None:
                groups = effect.groups
            else:
                assert effect.loot_ref is not None
                resolved = registry.resolve_loot_groups(effect.loot_ref)
                assert resolved is not None, (
                    f"loot_ref {effect.loot_ref!r} not found at runtime — "
                    "this should have been caught by _validate_loot_refs at load time."
                )
                groups = resolved

            # Build ExpressionContext if not already available.
            if ctx is None:
                from oscilla.engine.templates import ExpressionContext, GameContext, PlayerContext

                game_spec = registry.game.spec if registry.game is not None else None
                hemisphere = game_spec.season_hemisphere if game_spec is not None else "northern"
                timezone = game_spec.timezone if game_spec is not None else None
                ctx = ExpressionContext(
                    player=PlayerContext.from_character(player),
                    game=GameContext(season_hemisphere=hemisphere, timezone=timezone),
                )

            drop_results = _resolve_loot_groups(groups=groups, player=player, registry=registry, ctx=ctx)

            # Add items to inventory and collect totals for announcement.
            item_totals: Counter[str] = Counter()
            for item_ref, amount in drop_results:
                if amount > 0:
                    player.add_item(ref=item_ref, quantity=amount, registry=registry)
                    item_totals[item_ref] += amount
            if item_totals:
                parts = []
                for item_ref, total_qty in item_totals.items():
                    item = registry.items.get(item_ref)
                    name = item.spec.displayName if item is not None else item_ref
                    parts.append(f"{name} \u00d7 {total_qty}" if total_qty > 1 else name)
                await tui.show_text(f"You found: {', '.join(parts)}")

        case MilestoneGrantEffect(milestone=milestone):
            player.grant_milestone(milestone)
            # Quest stage advancement is evaluated after every milestone grant.
            # This is the primary runtime trigger for quest progression.
            from oscilla.engine.quest_engine import evaluate_quest_advancements

            await evaluate_quest_advancements(player=player, registry=registry, tui=tui)

        case QuestActivateEffect(quest_ref=quest_ref):
            if quest_ref in player.completed_quests:
                logger.warning("quest_activate: %r is already completed — no-op.", quest_ref)
                return
            if quest_ref in player.active_quests:
                logger.warning("quest_activate: %r is already active — no-op.", quest_ref)
                return
            quest_manifest = registry.quests.get(quest_ref)
            if quest_manifest is None:
                logger.error("quest_activate: quest %r not found in registry — skipping.", quest_ref)
                await tui.show_text(f"[red]Error: quest {quest_ref!r} not found.[/red]")
                return
            entry_stage = quest_manifest.spec.entry_stage
            player.active_quests[quest_ref] = entry_stage
            display_name = quest_manifest.spec.displayName
            await tui.show_text(f"[bold]Quest started:[/bold] {display_name}")
            # Immediately evaluate advancement — the entry stage might already be
            # satisfiable if the player already holds any advance_on milestones.
            from oscilla.engine.quest_engine import evaluate_quest_advancements

            await evaluate_quest_advancements(player=player, registry=registry, tui=tui)

        case EndAdventureEffect(outcome=outcome):
            raise _EndSignal(outcome)

        case HealEffect(amount=amount, target=target):
            if target == "enemy":
                if combat is None:
                    logger.warning("heal with target='enemy' called outside combat — skipping effect.")
                    return
                if amount == "full":
                    # Enemy max_hp is not tracked; log warning and skip.
                    logger.warning("heal target='enemy' with amount='full' is not supported — skipping.")
                    return
                combat.enemy_hp = max(0, combat.enemy_hp + int(amount))
                await tui.show_text(f"Enemy healed for {amount}. (Enemy HP: {combat.enemy_hp})")
                return
            # — player target — hp and max_hp are declared stats, not CharacterState fields.
            hp_val = player.stats.get("hp")
            max_hp_val = player.stats.get("max_hp")
            if not isinstance(hp_val, int) or isinstance(hp_val, bool):
                logger.warning("heal effect: 'hp' stat missing or not an int stat — skipping.")
                return
            if not isinstance(max_hp_val, int) or isinstance(max_hp_val, bool):
                logger.warning("heal effect: 'max_hp' stat missing or not an int stat — skipping.")
                return
            before_hp = hp_val
            new_hp: int
            if amount == "full":
                new_hp = max_hp_val
            else:
                new_hp = min(hp_val + int(amount), max_hp_val)
            healed = new_hp - before_hp
            player.set_stat(name="hp", value=new_hp)
            if healed > 0:
                await tui.show_text(f"Restored {healed} HP. (HP: {new_hp} / {max_hp_val})")

        case StatChangeEffect(stat=stat, amount=amount, target=target):
            # String amounts are resolved to int by template resolution above.
            assert isinstance(amount, int), (
                f"Unexpected non-int stat change amount after template resolution: {amount!r}"
            )
            if target == "enemy":
                if combat is None:
                    logger.warning("stat_change with target='enemy' called outside combat — skipping effect.")
                    return
                combat.enemy_hp += amount
                # Enemy HP floor is 0.
                combat.enemy_hp = max(0, combat.enemy_hp)
                action = "damaged" if amount < 0 else "healed"
                await tui.show_text(f"Enemy {action} for {abs(amount)}. (Enemy HP: {combat.enemy_hp})")
                return
            # — player target (original logic) —
            if stat not in player.stats:
                await tui.show_text(f"[red]Error: stat {stat!r} not found[/red]")
                return
            old_value = player.stats[stat]
            # bool is a subclass of int; the isinstance guard keeps bool stats blocked.
            if not isinstance(old_value, int) or isinstance(old_value, bool):
                await tui.show_text(f"[red]Error: cannot change non-numeric stat {stat!r}[/red]")
                return
            raw_new = old_value + amount
            lo, hi = _resolve_stat_bounds(stat=stat, registry=registry)
            new_value = max(lo, min(hi, raw_new))
            if new_value != raw_new:
                logger.warning(
                    "stat_change on %r: attempted %d, clamped to %d (bounds %d..%d).",
                    stat,
                    raw_new,
                    new_value,
                    lo,
                    hi,
                )
                await tui.show_text(
                    f"[yellow]Warning: stat {stat!r} clamped to {new_value} (attempted {raw_new}).[/yellow]"
                )
            player.set_stat(name=stat, value=new_value)
            await tui.show_text(
                f"Changed {stat}: {old_value} → {new_value}"
            )  # Fire threshold triggers for the stored stat and recompute derived stats.
            await _fire_threshold_triggers(
                stat_name=stat,
                old_value=old_value,
                new_value=new_value,
                player=player,
                registry=registry,
            )
            if registry.template_engine is not None:
                await _recompute_derived_stats(
                    player=player, registry=registry, engine=registry.template_engine, tui=tui
                )
            displaced = cascade_unequip_invalid(player=player, registry=registry)
            for name in displaced:
                await tui.show_text(f"[yellow]⚠ {name} unequipped: requirements no longer met.[/yellow]")

        case StatSetEffect(stat=stat, value=value):
            if stat not in player.stats:
                await tui.show_text(f"[red]Error: stat {stat!r} not found[/red]")
                return
            old_value = player.stats[stat]
            # bool set — bypass integer bounds entirely; True/False are always valid.
            if isinstance(value, bool):
                player.stats[stat] = value
                await tui.show_text(f"Set {stat}: {old_value} → {value}")
                displaced = cascade_unequip_invalid(player=player, registry=registry)
                for name in displaced:
                    await tui.show_text(f"[yellow]⚠ {name} unequipped: requirements no longer met.[/yellow]")
                return
            if value is None:
                player.stats[stat] = None
                await tui.show_text(f"Set {stat}: {old_value} → None")
                displaced = cascade_unequip_invalid(player=player, registry=registry)
                for name in displaced:
                    await tui.show_text(f"[yellow]⚠ {name} unequipped: requirements no longer met.[/yellow]")
                return
            lo, hi = _resolve_stat_bounds(stat=stat, registry=registry)
            clamped = max(lo, min(hi, value))
            if clamped != value:
                logger.warning(
                    "stat_set on %r: attempted %d, clamped to %d (bounds %d..%d).",
                    stat,
                    value,
                    clamped,
                    lo,
                    hi,
                )
                await tui.show_text(
                    f"[yellow]Warning: stat {stat!r} clamped to {clamped} (attempted {value}).[/yellow]"
                )
            player.set_stat(name=stat, value=clamped)
            await tui.show_text(
                f"Set {stat}: {old_value} → {clamped}"
            )  # Fire threshold triggers for the stored stat and recompute derived stats.
            await _fire_threshold_triggers(
                stat_name=stat,
                old_value=old_value if isinstance(old_value, int) else None,
                new_value=clamped,
                player=player,
                registry=registry,
            )
            if registry.template_engine is not None:
                await _recompute_derived_stats(
                    player=player, registry=registry, engine=registry.template_engine, tui=tui
                )
            displaced = cascade_unequip_invalid(player=player, registry=registry)
            for name in displaced:
                await tui.show_text(f"[yellow]⚠ {name} unequipped: requirements no longer met.[/yellow]")

        case UseItemEffect(item=item_ref):
            item = registry.items.get(item_ref)
            if item is None:
                await tui.show_text(f"[red]Error: item {item_ref!r} not found[/red]")
                return

            # Verify the player has the item (stackable) or an instance of it
            if item.spec.stackable:
                if player.stacks.get(item_ref, 0) == 0:
                    await tui.show_text(f"[red]You do not have {item.spec.displayName}.[/red]")
                    return
            else:
                instance = next((inst for inst in player.instances if inst.item_ref == item_ref), None)
                if instance is None:
                    await tui.show_text(f"[red]You do not have {item.spec.displayName}.[/red]")
                    return

            await tui.show_text(f"You use {item.spec.displayName}.")

            # Apply use_effects
            for sub_effect in item.spec.use_effects:
                await run_effect(effect=sub_effect, player=player, registry=registry, tui=tui, combat=combat)

            # Decrement charges if the item has a charge counter.
            if not item.spec.stackable and item.spec.charges is not None:
                instance = next((inst for inst in player.instances if inst.item_ref == item_ref), None)
                if instance is not None and instance.charges_remaining is not None:
                    instance.charges_remaining -= 1
                    if instance.charges_remaining <= 0:
                        player.remove_instance(instance_id=instance.instance_id)
                        await tui.show_text(f"[yellow]{item.spec.displayName} has been used up.[/yellow]")

            # Consume the item if configured
            if item.spec.consumed_on_use:
                if item.spec.stackable:
                    player.remove_item(ref=item_ref, quantity=1)
                else:
                    instance = next((inst for inst in player.instances if inst.item_ref == item_ref), None)
                    if instance is not None:
                        player.remove_instance(instance_id=instance.instance_id)

        case SkillGrantEffect(skill=skill_ref):
            granted = player.grant_skill(skill_ref=skill_ref, registry=registry)
            if granted:
                skill = registry.skills.get(skill_ref)
                name = skill.spec.displayName if skill is not None else skill_ref
                await tui.show_text(f"You learned: {name}!")
            # Already-known — silent no-op (grant_skill returns False)

        case DispelEffect(label=label, target=target, permanent=permanent):
            if combat is None:
                # Outside combat there are no active effects to remove.
                logger.debug("dispel(%r) called outside combat — no-op.", label)
                return
            before = len(combat.active_effects)
            combat.active_effects = [
                ae for ae in combat.active_effects if not (ae.label == label and ae.target == target)
            ]
            removed = before - len(combat.active_effects)
            if removed > 0:
                await tui.show_text(f"[green]{removed} effect(s) with label {label!r} dispelled.[/green]")
            else:
                logger.debug("dispel(%r): no matching active effects found.", label)
            # When permanent, also clear the stored buff so it cannot re-enter future combats.
            if permanent:
                player.active_buffs = [sb for sb in player.active_buffs if sb.buff_ref != label]

        case ApplyBuffEffect(buff_ref=buff_ref, target=buff_target, variables=call_vars):
            if combat is None:
                # Buffs only make sense inside the combat turn loop.
                logger.warning("apply_buff(%r) called outside combat — skipping.", buff_ref)
                return
            buff_manifest = registry.buffs.get(buff_ref)
            if buff_manifest is None:
                logger.error("apply_buff: buff ref %r not found in registry — skipping.", buff_ref)
                await tui.show_text(f"[red]Error: buff {buff_ref!r} not found.[/red]")
                return
            spec = buff_manifest.spec
            # Merge manifest variable defaults with call-site overrides.
            resolved_vars: Dict[str, int] = {**spec.variables, **call_vars}

            def _resolve_percent(v: int | str) -> int:
                """Resolve a modifier percent — either a literal int or a variable name."""
                if isinstance(v, int):
                    return v
                if v in resolved_vars:
                    return resolved_vars[v]
                # Should never reach here when load-time validation passes.
                logger.error("apply_buff: variable %r not in resolved_vars — using 0.", v)
                return 0

            # Resolve priority: a string is a variable name; int is used directly.
            resolved_priority: int = (
                _resolve_percent(spec.priority) if isinstance(spec.priority, str) else int(spec.priority)
            )

            # Exclusion check: when an exclusion_group is set, block or replace.
            if spec.exclusion_group is not None:
                same_group = [
                    ae
                    for ae in combat.active_effects
                    if ae.exclusion_group == spec.exclusion_group and ae.target == buff_target
                ]
                if any(ae.priority >= resolved_priority for ae in same_group):
                    logger.debug(
                        "apply_buff(%r): blocked by equal-or-higher priority entry in exclusion_group %r.",
                        buff_ref,
                        spec.exclusion_group,
                    )
                    return
                # Evict lower-priority entries in replace mode.
                if spec.exclusion_mode == "replace" and same_group:
                    evict_labels = {ae.label for ae in same_group}
                    combat.active_effects = [
                        ae for ae in combat.active_effects if ae.label not in evict_labels or ae.target != buff_target
                    ]

            # Build resolved modifier copies with concrete int percent values.
            resolved_modifiers = [
                mod.model_copy(update={"percent": _resolve_percent(mod.percent)}) for mod in spec.modifiers
            ]

            # Resolve turns from BuffDuration (may be a template string or int).
            turns_value = spec.duration.turns
            resolved_turns: int = _resolve_percent(turns_value) if isinstance(turns_value, str) else int(turns_value)

            # Buff manifest name is used as the stable label for DispelEffect matching.
            combat.active_effects.append(
                ActiveCombatEffect(
                    source_skill=buff_manifest.metadata.name,
                    target=buff_target,
                    remaining_turns=resolved_turns,
                    per_turn_effects=list(spec.per_turn_effects),
                    modifiers=resolved_modifiers,
                    label=buff_manifest.metadata.name,
                    exclusion_group=spec.exclusion_group or "",
                    priority=resolved_priority,
                    exclusion_mode=spec.exclusion_mode,
                    is_persistent=spec.duration.is_persistent,
                    variables=dict(resolved_vars),
                )
            )
            await tui.show_text(f"[bold]{spec.displayName}[/bold] applied for {resolved_turns} turn(s).")

        case QuestFailEffect(quest_ref=quest_ref):
            if quest_ref not in player.active_quests:
                logger.warning("quest_fail: quest %r is not active — no-op.", quest_ref)
                return
            quest_manifest = registry.quests.get(quest_ref)
            if quest_manifest is None:
                logger.error("quest_fail: quest %r not found in registry — skipping.", quest_ref)
                await tui.show_text(f"[red]Error: quest {quest_ref!r} not found.[/red]")
                return
            stage_name = player.active_quests.pop(quest_ref)
            player.failed_quests.add(quest_ref)
            display_name = quest_manifest.spec.displayName
            await tui.show_text(f"[bold red]Quest failed: {display_name}[/bold red]")
            # Run fail_effects from the stage that was active at the time of failure.
            stage_map = {s.name: s for s in quest_manifest.spec.stages}
            stage = stage_map.get(stage_name)
            if stage is not None:
                for eff in stage.fail_effects:
                    await run_effect(effect=eff, player=player, registry=registry, tui=tui, combat=combat)

        case SetPronounsEffect(set=pronoun_key):
            from oscilla.engine.templates import resolve_pronoun_set

            ps = resolve_pronoun_set(key=pronoun_key, registry=registry)
            if ps is None:
                logger.warning("set_pronouns: unknown pronoun set key %r — skipping.", pronoun_key)
                await tui.show_text(f"[red]Error: unknown pronoun set {pronoun_key!r}[/red]")
                return
            player.pronouns = ps
            await tui.show_text(f"Pronouns set to {pronoun_key}.")

        case AdjustGameTicksEffect(delta=delta):
            if registry.game is None or registry.game.spec.time is None:
                logger.warning("adjust_game_ticks effect applied with no time system configured — ignoring.")
                return
            pre_epoch = registry.game.spec.time.pre_epoch_behavior
            new_ticks = player.game_ticks + delta
            if pre_epoch == "clamp":
                new_ticks = max(0, new_ticks)
            player.game_ticks = new_ticks
        case EmitTriggerEffect(trigger=trigger_name):
            # The loader verified this name is declared in triggers.custom.
            # If it has no registered adventures, this is a no-op (not an error).
            if registry.game is not None:
                player.enqueue_trigger(
                    trigger_name,
                    max_depth=registry.game.spec.triggers.max_trigger_queue_depth,
                )

        case PrestigeEffect():
            if registry.game is None or registry.game.spec.prestige is None:
                logger.error("prestige effect fired but no prestige: block is declared in game.yaml — skipping.")
                await tui.show_text("[red]Error: prestige not configured in game.yaml.[/red]")
                return

            prestige_cfg = registry.game.spec.prestige

            # 1. Run pre_prestige_effects against the CURRENT (old) state.
            for pre_eff in prestige_cfg.pre_prestige_effects:
                await run_effect(
                    effect=pre_eff,
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=combat,
                    ctx=ctx,
                )

            # 2. Snapshot carried stat, skill, and milestone values AFTER pre-effects run
            #    so legacy bonuses already granted are captured in the carry.
            carried_stats: Dict[str, int | bool | None] = {
                stat: player.stats.get(stat) for stat in prestige_cfg.carry_stats if stat in player.stats
            }
            carried_skills: Set[str] = player.known_skills & set(prestige_cfg.carry_skills)
            # milestones is now Dict[str, GrantRecord] — intersect on keys.
            carried_milestones: Dict[str, Any] = {
                k: v for k, v in player.milestones.items() if k in prestige_cfg.carry_milestones
            }

            # 3. Reset in-memory state to character_config defaults.
            if registry.character_config is None:
                logger.error("prestige effect: character_config not available in registry — skipping reset.")
                return
            all_stats = registry.character_config.spec.public_stats + registry.character_config.spec.hidden_stats
            player.character_class = None
            player.current_location = None
            player.milestones = {}
            player.stacks = {}
            player.instances = []
            player.equipment = {}
            player.active_quests = {}
            player.completed_quests = set()
            player.failed_quests = set()
            player.known_skills = set()
            player.skill_tick_expiry = {}
            player.skill_real_expiry = {}
            player.adventure_last_completed_real_ts = {}
            player.adventure_last_completed_game_ticks = {}
            player.adventure_last_completed_at_ticks = {}
            player.internal_ticks = 0
            player.game_ticks = 0
            player.era_started_at_ticks = {}
            player.era_ended_at_ticks = {}
            player.stats = {s.name: s.default for s in all_stats}

            # 4. Apply carry-forward: overwrite reset values with carried ones.
            for stat_name, value in carried_stats.items():
                player.stats[stat_name] = value
            player.known_skills = carried_skills
            player.milestones = carried_milestones

            # 5. Increment prestige_count.
            player.prestige_count += 1

            # 6. Run post_prestige_effects against the NEW (reset + carried) state.
            for post_eff in prestige_cfg.post_prestige_effects:
                await run_effect(
                    effect=post_eff,
                    player=player,
                    registry=registry,
                    tui=tui,
                    combat=combat,
                    ctx=ctx,
                )

            # 7. Signal the session layer to perform the DB iteration transition at adventure_end.
            player.prestige_pending = PrestigeCarryForward(
                carry_stats=list(prestige_cfg.carry_stats),
                carry_skills=list(prestige_cfg.carry_skills),
            )

            await tui.show_text(f"[bold]Your journey begins anew.[/bold] (Prestige {player.prestige_count})")

        case SetNameEffect(prompt=prompt):
            chosen: str = await tui.input_text(prompt)
            player.name = chosen.strip()

        case ArchetypeAddEffect(name=archetype_name, force=force):
            already_held = archetype_name in player.archetypes
            if not already_held or force:
                archetype_manifest = registry.archetypes.get(archetype_name)
                if archetype_manifest is not None:
                    for gain_eff in archetype_manifest.spec.gain_effects:
                        await run_effect(
                            effect=gain_eff,
                            player=player,
                            registry=registry,
                            tui=tui,
                            combat=combat,
                            ctx=ctx,
                        )
                player.archetypes[archetype_name] = player.make_grant_record()

        case ArchetypeRemoveEffect(name=archetype_name, force=force):
            currently_held = archetype_name in player.archetypes
            if currently_held or force:
                archetype_manifest = registry.archetypes.get(archetype_name)
                if archetype_manifest is not None:
                    for lose_eff in archetype_manifest.spec.lose_effects:
                        await run_effect(
                            effect=lose_eff,
                            player=player,
                            registry=registry,
                            tui=tui,
                            combat=combat,
                            ctx=ctx,
                        )
                player.archetypes.pop(archetype_name, None)

        case SkillRevokeEffect(skill=skill_ref):
            player.known_skills.discard(skill_ref)

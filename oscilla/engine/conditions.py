"""Condition evaluator — pure recursive evaluation of condition trees against player state."""

from __future__ import annotations

import datetime
from logging import getLogger
from typing import TYPE_CHECKING

from oscilla.engine import calendar_utils
from oscilla.engine.models.base import (
    AdventuresCompletedCondition,
    AllCondition,
    AnyCondition,
    AnyItemEquippedCondition,
    ArchetypeCountCondition,
    ArchetypeTicksElapsedCondition,
    CharacterStatCondition,
    ChineseZodiacIsCondition,
    Condition,
    DateBetweenCondition,
    DateIsCondition,
    DayOfWeekIsCondition,
    EnemiesDefeatedCondition,
    GameCalendarCycleCondition,
    GameCalendarEraCondition,
    GameCalendarTimeCondition,
    HasAllArchetypesCondition,
    HasAnyArchetypeCondition,
    HasArchetypeCondition,
    ItemCondition,
    ItemEquippedCondition,
    ItemHeldLabelCondition,
    LevelCondition,
    LocationsVisitedCondition,
    MilestoneCondition,
    MilestoneTicksElapsedCondition,
    MonthIsCondition,
    MoonPhaseIsCondition,
    NameEqualsCondition,
    NotCondition,
    PrestigeCountCondition,
    PronounsCondition,
    QuestStageCondition,
    SeasonIsCondition,
    SkillCondition,
    TimeBetweenCondition,
    ZodiacIsCondition,
)

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)


def _current_datetime(registry: "ContentRegistry | None") -> datetime.datetime:
    """Return the current datetime in the game's configured timezone."""
    tz_name: str | None = None
    if registry is not None and registry.game is not None:
        tz_name = registry.game.spec.timezone
    return calendar_utils.resolve_local_datetime(tz_name)


def evaluate(
    condition: Condition | None,
    player: "CharacterState",
    registry: "ContentRegistry | None" = None,
    exclude_item: str | None = None,
) -> bool:
    """Evaluate a condition tree against the given player state.

    Returns True if condition is None (no gate) or every node evaluates to True.
    Pass registry to enable equipment-aware stat evaluation via effective_stats().

    exclude_item: when set, the named item's stat bonuses are excluded from
    effective_stats() lookups. Used for the self-justification guard when
    evaluating EquipSpec.requires.
    """
    if condition is None:
        return True

    match condition:
        # --- Branch nodes ---
        case AllCondition(conditions=children):
            return all(evaluate(c, player, registry, exclude_item) for c in children)
        case AnyCondition(conditions=children):
            return any(evaluate(c, player, registry, exclude_item) for c in children)
        case NotCondition(condition=child):
            return not evaluate(child, player, registry, exclude_item)

        # --- Player attribute leaves ---
        case LevelCondition(value=v):
            # level is now a regular stat; fall back to 0 if the game doesn't declare it.
            return int(player.stats.get("level") or 0) >= v
        case MilestoneCondition(name=n):
            return n in player.milestones
        case MilestoneTicksElapsedCondition() as c:
            record = player.milestones.get(c.name)
            if record is None:
                return False
            elapsed = player.internal_ticks - record.tick
            if c.gte is not None and elapsed < c.gte:
                return False
            if c.lte is not None and elapsed > c.lte:
                return False
            return True
        case HasArchetypeCondition(name=n):
            return n in player.archetypes
        case HasAllArchetypesCondition(names=ns):
            return all(n in player.archetypes for n in ns)
        case HasAnyArchetypeCondition(names=ns):
            return any(n in player.archetypes for n in ns)
        case ArchetypeCountCondition() as c:
            return _numeric_compare(len(player.archetypes), c)
        case ArchetypeTicksElapsedCondition() as c:
            record = player.archetypes.get(c.name)
            if record is None:
                return False
            elapsed = player.internal_ticks - record.tick
            if c.gte is not None and elapsed < c.gte:
                return False
            if c.lte is not None and elapsed > c.lte:
                return False
            return True
        case ItemCondition(name=n):
            # Fixed: check both stackable items and non-stackable instances.
            in_stacks = player.stacks.get(n, 0) > 0
            in_instances = any(inst.item_ref == n for inst in player.instances)
            return in_stacks or in_instances
        case PrestigeCountCondition() as c:
            return _numeric_compare(player.prestige_count, c)

        # --- Item equipment/label predicates ---
        case ItemEquippedCondition(name=n):
            # True when the named non-stackable item is currently in an equipment slot.
            equipped_ids = set(player.equipment.values())
            return any(inst.item_ref == n and inst.instance_id in equipped_ids for inst in player.instances)
        case ItemHeldLabelCondition(label=lbl):
            # True when any held item (stack or instance) has the given label.
            if registry is None:
                logger.warning("item_held_label condition on %r requires registry — evaluating False.", lbl)
                return False
            for item_ref in player.stacks:
                item = registry.items.get(item_ref)
                if item is not None and lbl in item.spec.labels:
                    return True
            for inst in player.instances:
                item = registry.items.get(inst.item_ref)
                if item is not None and lbl in item.spec.labels:
                    return True
            return False
        case AnyItemEquippedCondition(label=lbl):
            # True when any equipped item instance has the given label.
            if registry is None:
                logger.warning("any_item_equipped condition on %r requires registry — evaluating False.", lbl)
                return False
            equipped_ids = set(player.equipment.values())
            for inst in player.instances:
                if inst.instance_id not in equipped_ids:
                    continue
                item = registry.items.get(inst.item_ref)
                if item is not None and lbl in item.spec.labels:
                    return True
            return False

        # --- CharacterConfig stat leaves ---
        case CharacterStatCondition(name=n, stat_source=stat_source) as c:
            # Use base stats when stat_source is "base" or registry is unavailable.
            if stat_source == "base" or registry is None:
                stats = player.stats
            else:
                stats = player.effective_stats(registry=registry, exclude_item=exclude_item)
            value = stats.get(n, 0)
            # Stats may be bool; only numeric stats are comparable.
            if not isinstance(value, int):
                logger.warning(
                    "character_stat condition on non-numeric stat %r (value=%r); treating as 0",
                    n,
                    value,
                )
                return _numeric_compare(0, c)
            return _numeric_compare(value, c)

        # --- Statistics leaves ---
        case EnemiesDefeatedCondition(name=n) as c:
            return _numeric_compare(player.statistics.enemies_defeated.get(n, 0), c)
        case LocationsVisitedCondition(name=n) as c:
            return _numeric_compare(player.statistics.locations_visited.get(n, 0), c)
        case AdventuresCompletedCondition(name=n) as c:
            return _numeric_compare(player.statistics.adventures_completed.get(n, 0), c)

        # --- Skill leaves ---
        case SkillCondition(name=n, mode=mode):
            if mode == "learned":
                # Only permanently learned skills — registry not required.
                return n in player.known_skills
            else:
                # mode == "available": includes item-granted skills; requires registry.
                # Without a registry (e.g. some test contexts) falls back to known_skills only.
                return n in player.available_skills(registry)

        # --- Pronoun leaves ---
        case PronounsCondition(set=pronoun_key):
            from oscilla.engine.templates import resolve_pronoun_set

            target_ps = resolve_pronoun_set(key=pronoun_key, registry=registry)
            if target_ps is None:
                logger.warning(
                    "pronouns condition: unknown pronoun set key %r — evaluating False.",
                    pronoun_key,
                )
                return False
            return player.pronouns == target_ps

        # --- Quest leaf ---
        case QuestStageCondition(quest=q, stage=s):
            return player.active_quests.get(q) == s

        case NameEqualsCondition(value=v):
            return player.name == v

        # --- Calendar predicates ---
        # All predicates derive date/time from a single call so that all
        # conditions see a consistent moment in the game's configured timezone.
        case SeasonIsCondition(value=v):
            today = _current_datetime(registry).date()
            # Read hemisphere from game config when available; default to northern.
            hemisphere = "northern"
            if registry is not None and registry.game is not None:
                hemisphere = registry.game.spec.season_hemisphere
            elif registry is None:
                logger.debug("season_is condition evaluated without a registry — defaulting to northern hemisphere.")
            return calendar_utils.season(today, hemisphere=hemisphere) == v

        case MoonPhaseIsCondition(value=v):
            return calendar_utils.moon_phase(_current_datetime(registry).date()) == v

        case ZodiacIsCondition(value=v):
            return calendar_utils.zodiac_sign(_current_datetime(registry).date()) == v

        case ChineseZodiacIsCondition(value=v):
            return calendar_utils.chinese_zodiac(_current_datetime(registry).date().year) == v

        case MonthIsCondition(value=v):
            # value is always int (normalized by model validator).
            return _current_datetime(registry).date().month == v

        case DayOfWeekIsCondition(value=v):
            # value is always int 0-6 (normalized by model validator), matching
            # Python's date.weekday() convention (Monday=0, Sunday=6).
            return _current_datetime(registry).date().weekday() == v

        case DateIsCondition(month=m, day=d, year=y):
            today = _current_datetime(registry).date()
            if y is not None and today.year != y:
                return False
            return today.month == m and today.day == d

        case DateBetweenCondition(start=start, end=end):
            today = _current_datetime(registry).date()
            start_md = (start.month, start.day)
            end_md = (end.month, end.day)
            today_md = (today.month, today.day)

            if start_md == end_md:
                # Zero-duration range — always false.
                logger.warning(
                    "date_between has identical start and end (%d-%02d) — always false.",
                    start.month,
                    start.day,
                )
                return False

            if start_md <= end_md:
                # Normal within-year window.
                return start_md <= today_md <= end_md
            else:
                # Year-wrapping window (e.g. Dec 1 – Jan 31): true when >= start OR <= end.
                return today_md >= start_md or today_md <= end_md

        case TimeBetweenCondition(start=start_str, end=end_str):
            now_time = _current_datetime(registry).time()
            # fromisoformat() handles HH:MM; pattern validation already ensures the format.
            t_start = datetime.time.fromisoformat(start_str)
            t_end = datetime.time.fromisoformat(end_str)

            if t_start == t_end:
                # Zero-duration window — always false.
                logger.warning(
                    "time_between condition has identical start and end (%s) — always false.",
                    start_str,
                )
                return False

            if t_start < t_end:
                # Normal same-day window.
                return t_start <= now_time <= t_end
            else:
                # Midnight-wrapping window: true when >= start OR <= end.
                return now_time >= t_start or now_time <= t_end

        # --- In-game calendar predicates ---

        case GameCalendarTimeCondition() as c:
            # Evaluate False with warning when time system is not configured.
            if registry is None or registry.game is None or registry.game.spec.time is None:
                logger.warning(
                    "game_calendar_time_is condition evaluated without a configured time system — returning False."
                )
                return False
            resolver = registry.ingame_time_resolver
            if resolver is None:
                return False
            view = resolver.resolve(
                game_ticks=player.game_ticks,
                internal_ticks=player.internal_ticks,
                player=player,
                registry=registry,
            )
            tick_value = view.internal_ticks if c.clock == "internal" else view.game_ticks
            return _numeric_compare(tick_value, c)

        case GameCalendarCycleCondition(cycle=cycle_name, value=expected_value):
            if registry is None or registry.game is None or registry.game.spec.time is None:
                logger.warning(
                    "game_calendar_cycle_is condition on %r evaluated without time system — returning False.",
                    cycle_name,
                )
                return False
            resolver = registry.ingame_time_resolver
            if resolver is None:
                return False
            view = resolver.resolve(
                game_ticks=player.game_ticks,
                internal_ticks=player.internal_ticks,
                player=player,
                registry=registry,
            )
            state = view.cycle(cycle_name)
            if state is None:
                logger.warning(
                    "game_calendar_cycle_is: cycle %r not found in time system — returning False.",
                    cycle_name,
                )
                return False
            return state.label == expected_value

        case GameCalendarEraCondition(era=era_name, state=expected_state):
            if registry is None or registry.game is None or registry.game.spec.time is None:
                logger.warning(
                    "game_calendar_era_is condition on %r evaluated without time system — returning False.",
                    era_name,
                )
                return False
            resolver = registry.ingame_time_resolver
            if resolver is None:
                return False
            view = resolver.resolve(
                game_ticks=player.game_ticks,
                internal_ticks=player.internal_ticks,
                player=player,
                registry=registry,
            )
            era_state = view.era(era_name)
            if era_state is None:
                logger.warning(
                    "game_calendar_era_is: era %r not found — returning False.",
                    era_name,
                )
                return False
            is_active = era_state.active
            return is_active if expected_state == "active" else not is_active

    # Unreachable if all Condition subtypes are handled above; guards against
    # extending the union without adding a case branch.
    raise ValueError(f"Unhandled condition type: {condition!r}")  # pragma: no cover


def _numeric_compare(value: int, condition: object) -> bool:
    """Apply gt / gte / lt / lte / eq / mod comparisons from a condition object.

    All comparators that are set must pass (logical AND).
    Raises ValueError if no comparators are set — this should have been caught
    by the Pydantic model_validator at load time, but serves as a runtime guard.
    """
    have_gt = getattr(condition, "gt", None)
    have_gte = getattr(condition, "gte", None)
    have_lt = getattr(condition, "lt", None)
    have_lte = getattr(condition, "lte", None)
    have_eq = getattr(condition, "eq", None)
    have_mod = getattr(condition, "mod", None)

    if all(v is None for v in (have_gt, have_gte, have_lt, have_lte, have_eq, have_mod)):
        raise ValueError(
            f"Numeric condition {condition!r} has none of gt/gte/lt/lte/eq/mod set — "
            "at least one comparator is required."
        )

    if have_gt is not None and not (value > have_gt):
        return False
    if have_gte is not None and not (value >= have_gte):
        return False
    if have_lt is not None and not (value < have_lt):
        return False
    if have_lte is not None and not (value <= have_lte):
        return False
    if have_eq is not None and not (value == have_eq):
        return False
    if have_mod is not None and not (value % have_mod.divisor == have_mod.remainder):
        return False
    return True

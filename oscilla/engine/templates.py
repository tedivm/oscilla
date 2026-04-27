"""Jinja2-based dynamic content template engine for Oscilla.

Templates are precompiled at content load time and rendered at runtime with a
read-only ExpressionContext derived from CharacterState. Any error at compile
or mock-render time is raised as TemplateValidationError. Any error at runtime
is a hard TemplateRuntimeError — if comprehensive validation passes, this
should never fire.
"""

from __future__ import annotations

import datetime
import math
import random
import re
from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Set

from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from oscilla.engine import calendar_utils

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.ingame_time import InGameTimeView

logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Pronoun data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PronounSet:
    """All grammatical forms of a pronoun set for template use.

    All fields are lowercase; templates apply | capitalize or | upper as needed
    via the pronoun placeholder preprocessor.
    """

    subject: str  # they / she / he
    object: str  # them / her / him
    possessive: str  # their / her / his
    possessive_standalone: str  # theirs / hers / his
    reflexive: str  # themselves / herself / himself

    # Singular/plural flag — controls verb agreement for "they/them" set.
    # True for "they" (plural verbs), False for "she"/"he" (singular verbs).
    uses_plural_verbs: bool


# Predefined sets. Games can define additional sets in CharacterConfig.
PRONOUN_SETS: Dict[str, PronounSet] = {
    "they_them": PronounSet(
        subject="they",
        object="them",
        possessive="their",
        possessive_standalone="theirs",
        reflexive="themselves",
        uses_plural_verbs=True,
    ),
    "she_her": PronounSet(
        subject="she",
        object="her",
        possessive="her",
        possessive_standalone="hers",
        reflexive="herself",
        uses_plural_verbs=False,
    ),
    "he_him": PronounSet(
        subject="he",
        object="him",
        possessive="his",
        possessive_standalone="his",
        reflexive="himself",
        uses_plural_verbs=False,
    ),
}

DEFAULT_PRONOUN_SET = PRONOUN_SETS["they_them"]


def resolve_pronoun_set(key: str, registry: "Any | None" = None) -> "PronounSet | None":
    """Resolve a pronoun set key to a PronounSet.

    Checks the built-in PRONOUN_SETS first, then the game's extra_pronoun_sets
    declared in CharacterConfig. Returns None if the key is not found anywhere.
    """
    ps = PRONOUN_SETS.get(key)
    if ps is not None:
        return ps
    if registry is not None:
        char_config = getattr(registry, "character_config", None)
        if char_config is not None:
            for ps_def in char_config.spec.extra_pronoun_sets:
                if ps_def.name == key:
                    return PronounSet(
                        subject=ps_def.subject,
                        object=ps_def.object,
                        possessive=ps_def.possessive,
                        possessive_standalone=ps_def.possessive_standalone,
                        reflexive=ps_def.reflexive,
                        uses_plural_verbs=ps_def.uses_plural_verbs,
                    )
    return None


# ---------------------------------------------------------------------------
# Pronoun placeholder preprocessor
# ---------------------------------------------------------------------------

# Verb pairs: (singular, plural) — both forms map to the same conditional.
_VERB_PAIRS: Dict[str, tuple[str, str]] = {
    "is": ("is", "are"),
    "are": ("is", "are"),
    "was": ("was", "were"),
    "were": ("was", "were"),
    "has": ("has", "have"),
    "have": ("has", "have"),
}

# Pronoun fields: base word → PronounSet attribute name
_PRONOUN_FIELDS: Dict[str, str] = {
    "they": "subject",
    "them": "object",
    "their": "possessive",
    "theirs": "possessive_standalone",
    "themselves": "reflexive",
}


def _cap_filter(word: str) -> str:
    """Determine Jinja2 filter suffix for the capitalisation pattern of word.

    'they'  → '' (no filter — values already lowercase)
    'They'  → ' | capitalize'
    'THEY'  → ' | upper'
    """
    if word.isupper():
        return " | upper"
    if word[0].isupper():
        return " | capitalize"
    return ""


def preprocess_pronouns(template_str: str) -> str:
    """Replace {pronoun} and {verb} placeholders with Jinja2 expressions.

    Handles any capitalisation pattern:
      {they}       →  {{ player.pronouns.subject }}
      {They}       →  {{ player.pronouns.subject | capitalize }}
      {THEY}       →  {{ player.pronouns.subject | upper }}
      {is}/{are}   →  {{ ('is' if not player.pronouns.uses_plural_verbs else 'are') }}

    Unrecognised {word} patterns are left unchanged so that normal Jinja2
    blocks like {% if %} are not affected.
    """

    def replace(match: re.Match[str]) -> str:
        word = match.group(1)
        base = word.lower()
        cap = _cap_filter(word)

        if base in _PRONOUN_FIELDS:
            attr = _PRONOUN_FIELDS[base]
            return "{{{{ player.pronouns.{attr}{cap} }}}}".format(attr=attr, cap=cap)

        if base in _VERB_PAIRS:
            singular, plural = _VERB_PAIRS[base]
            # Emit conditional that chooses correct verb form, then applies cap filter.
            expr = f"('{singular}' if not player.pronouns.uses_plural_verbs else '{plural}')"
            if cap:
                jinja_filter = cap.strip().lstrip("| ").strip()
                return "{{{{ ({expr}) | {jinja_filter} }}}}".format(expr=expr, jinja_filter=jinja_filter)
            return "{{{{ {expr} }}}}".format(expr=expr)

        # Not a recognised placeholder — leave the braces as-is.
        return str(match.group(0))

    return re.sub(r"\{([A-Za-z]+)\}", replace, template_str)


# ---------------------------------------------------------------------------
# Read-only template context objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlayerPronounView:
    """Read-only pronoun view exposed to templates as player.pronouns."""

    subject: str
    object: str
    possessive: str
    possessive_standalone: str
    reflexive: str
    uses_plural_verbs: bool

    @classmethod
    def from_set(cls, ps: PronounSet) -> "PlayerPronounView":
        return cls(
            subject=ps.subject,
            object=ps.object,
            possessive=ps.possessive,
            possessive_standalone=ps.possessive_standalone,
            reflexive=ps.reflexive,
            uses_plural_verbs=ps.uses_plural_verbs,
        )


@dataclass(frozen=True)
class PlayerMilestoneView:
    """Read-only milestone view exposed to templates as player.milestones.

    Accepts either a Set[str] or a Dict[str, ...] for backward-compat during migration.
    Templates should only use player.milestones.has(name).
    """

    _milestones: "Set[str] | Dict[str, Any]" = field(default_factory=set)

    def has(self, name: str) -> bool:
        return name in self._milestones


@dataclass(frozen=True)
class PlayerContext:
    """Read-only projection of CharacterState for template rendering.

    Exposing only safe scalar fields and view objects prevents templates from
    accidentally (or deliberately) mutating game state.
    """

    name: str
    prestige_count: int
    # level, hp, max_hp removed — these are now in stats if the game declares them.
    # Templates use player.stats["level"] etc.
    stats: Dict[str, int | bool | None]
    milestones: PlayerMilestoneView
    pronouns: PlayerPronounView

    def get(self, key: str, default: "int | bool | None" = None) -> "int | bool | None":
        """Convenience shorthand for player.stats.get(key, default).

        Allows templates to use player.get('strength', 5) in ExpressionContext,
        matching the player dict API used in CombatFormulaContext.
        """
        return self.stats.get(key, default)

    @classmethod
    def from_character(cls, char: "CharacterState") -> "PlayerContext":
        # Merge stored stats with current derived stat shadow values so templates
        # see derived stats via player.stats["name"] like any other stat.
        merged_stats: Dict[str, int | bool | None] = dict(char.stats)
        merged_stats.update(char._derived_shadows)
        return cls(
            name=char.name,
            prestige_count=char.prestige_count,
            stats=merged_stats,
            milestones=PlayerMilestoneView(_milestones=char.milestones),
            pronouns=PlayerPronounView.from_set(char.pronouns),
        )


@dataclass(frozen=True)
class CombatContextView:
    """Read-only combat state exposed to templates as combat.

    Only present when a template is rendered inside a CombatStep handler.
    """

    enemy_stats: Dict[str, int]
    enemy_name: str
    turn: int
    combat_stats: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class GameContext:
    """Read-only projection of GameSpec for template rendering.

    Exposes season_hemisphere (for hemisphere-correct season() results) and
    timezone (for timezone-aware today(), now(), and season() results).
    Authors should not need to pass either as template arguments.
    """

    season_hemisphere: str = "northern"
    timezone: str | None = None

    def __getattr__(self, name: str) -> "Any":
        raise AttributeError(f"game has no attribute {name!r}")


@dataclass
class ExpressionContext:
    """Complete read-only context passed to every template render call.

    combat is None for non-combat steps. Templates that reference combat.*
    will raise UndefinedError at mock-render time if the context_type is not
    'combat', which is caught as a validation error at load time.

    game carries game-level configuration (e.g. season_hemisphere) so that
    template functions can adapt to game settings without explicit parameters.

    ingame_time is None when the time system is not configured. Templates
    must guard with {% if ingame_time %} before accessing it.

    this exposes the current manifest's properties dict for template access.
    """

    player: PlayerContext
    combat: CombatContextView | None = None
    game: GameContext = field(default_factory=GameContext)
    ingame_time: "InGameTimeView | None" = None
    # Properties from the current manifest (adventure, item, etc.). Empty when not applicable.
    this: Dict[str, int | float | str | bool] = field(default_factory=dict)


@dataclass
class CombatFormulaContext:
    """Context passed to formula rendering during a combat encounter.

    Provides the numeric values available to Jinja2 formula strings:
    - ``player``: effective player stats (e.g. ``player["strength"]``).
    - ``enemy_stats``: mutable enemy stats from ``CombatContext.enemy_stats``.
    - ``combat_stats``: transient per-combat values from ``CombatContext.combat_stats``.
    - ``turn_number``: current combat turn (1-indexed).
    - ``this``: properties from the triggering manifest (item, skill, or enemy).
    """

    player: Dict[str, int]
    enemy_stats: Dict[str, int]
    combat_stats: Dict[str, int]
    turn_number: int
    # Properties from the triggering manifest (item, skill, or enemy). Empty when not applicable.
    this: Dict[str, int | float | str | bool] = field(default_factory=dict)


class FormulaRenderError(Exception):
    """Raised when a combat damage formula fails to render or produces a non-int result."""


def render_formula(formula: str, ctx: CombatFormulaContext) -> int:
    """Render a Jinja2 formula string in a CombatFormulaContext and return an int.

    The formula may contain ``{% set %}`` blocks before the ``{{ }}`` output
    expression. All ``SAFE_GLOBALS`` are available alongside ``player``,
    ``enemy_stats``, ``combat_stats``, and ``turn_number`` from the context.

    Raises ``FormulaRenderError`` on Jinja2 errors or if the result cannot be
    coerced to ``int``.
    """
    from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

    env = Environment(undefined=StrictUndefined)  # noqa: S701 - safe globals restrict execution
    render_ctx: Dict[str, Any] = {}
    render_ctx.update(SAFE_GLOBALS)
    render_ctx["player"] = ctx.player
    render_ctx["enemy_stats"] = ctx.enemy_stats
    render_ctx["combat_stats"] = ctx.combat_stats
    render_ctx["turn_number"] = ctx.turn_number
    render_ctx["this"] = ctx.this

    try:
        template = env.from_string(formula)
        result = template.render(**render_ctx)
    except (TemplateSyntaxError, UndefinedError) as exc:
        raise FormulaRenderError(f"Formula render failed: {exc}") from exc

    try:
        return int(result)
    except (ValueError, TypeError) as exc:
        raise FormulaRenderError(f"Formula produced non-integer result {result!r}: {exc}") from exc


# ---------------------------------------------------------------------------
# Built-in safe functions
# ---------------------------------------------------------------------------


def _safe_roll(low: int, high: int) -> int:
    """Return a random integer N such that low <= N <= high (inclusive).

    Raises ValueError on invalid arguments.
    """
    if not isinstance(low, int) or not isinstance(high, int):
        raise ValueError(f"roll() requires int arguments, got {type(low).__name__}, {type(high).__name__}")
    if low > high:
        raise ValueError(f"roll({low}, {high}): low must be <= high")
    return random.randint(low, high)


def _safe_choice(items: list) -> Any:  # noqa: ANN401
    """Return a random element from items.

    Raises ValueError on empty list.
    """
    if not items:
        raise ValueError("choice() called with empty list")
    return random.choice(items)


def _safe_random() -> float:
    """Return a random float in [0.0, 1.0)."""
    return random.random()


def _now() -> datetime.datetime:
    """Return the current local date and time."""
    return datetime.datetime.now()


def _today() -> datetime.date:
    """Return the current local date."""
    return datetime.date.today()


def _safe_sample(items: list, k: int) -> list:  # noqa: ANN401
    """Return k unique elements chosen from items without replacement.

    Raises ValueError if k > len(items) or k < 0.
    """
    if not items:
        raise ValueError("sample() called with empty list")
    if k < 0 or k > len(items):
        raise ValueError(f"sample(): k={k} is out of range for a list of length {len(items)}")
    return random.sample(items, k)


def _clamp(value: int | float, lo: int | float, hi: int | float) -> int | float:
    """Clamp value to the inclusive range [lo, hi].

    Raises ValueError if lo > hi.
    """
    if lo > hi:
        raise ValueError(f"clamp(): lo={lo} must be <= hi={hi}")
    return max(lo, min(hi, value))


# Common real-world time multiples for use in template expressions (e.g. seconds: "{{ SECONDS_PER_DAY }}")
SECONDS_PER_MINUTE: int = 60
SECONDS_PER_HOUR: int = 3_600
SECONDS_PER_DAY: int = 86_400
SECONDS_PER_WEEK: int = 604_800


# ---------------------------------------------------------------------------
# Dice pool functions
# ---------------------------------------------------------------------------


def _safe_roll_pool(n: int, sides: int) -> List[int]:
    """Roll n dice each with the given number of sides. Returns the individual results.

    Example: roll_pool(3, 6) might return [2, 5, 1] for 3d6.
    """
    if not isinstance(n, int) or not isinstance(sides, int):
        raise ValueError("roll_pool() requires int arguments")
    if n < 1:
        raise ValueError(f"roll_pool(): n must be >= 1, got {n}")
    if sides < 2:
        raise ValueError(f"roll_pool(): sides must be >= 2, got {sides}")
    return [random.randint(1, sides) for _ in range(n)]


def _safe_keep_highest(pool: List[int], n: int) -> List[int]:
    """Return the n highest values from pool (sorted descending).

    Example: keep_highest([1, 5, 3, 4], 2) returns [5, 4].
    Used for advantage mechanics: keep_highest(roll_pool(2, 20), 1).
    """
    if not isinstance(pool, list):
        raise ValueError("keep_highest(): first argument must be a list")
    if not isinstance(n, int) or n < 1:
        raise ValueError(f"keep_highest(): n must be a positive int, got {n!r}")
    if n > len(pool):
        raise ValueError(f"keep_highest(): n={n} exceeds pool length {len(pool)}")
    return sorted(pool, reverse=True)[:n]


def _safe_keep_lowest(pool: List[int], n: int) -> List[int]:
    """Return the n lowest values from pool (sorted ascending).

    Example: keep_lowest([1, 5, 3, 4], 2) returns [1, 3].
    Used for disadvantage mechanics: keep_lowest(roll_pool(2, 20), 1).
    """
    if not isinstance(pool, list):
        raise ValueError("keep_lowest(): first argument must be a list")
    if not isinstance(n, int) or n < 1:
        raise ValueError(f"keep_lowest(): n must be a positive int, got {n!r}")
    if n > len(pool):
        raise ValueError(f"keep_lowest(): n={n} exceeds pool length {len(pool)}")
    return sorted(pool)[:n]


def _safe_count_successes(pool: List[int], threshold: int) -> int:
    """Count the number of dice in pool that are >= threshold.

    Example: count_successes([3, 5, 2, 6], 5) returns 2.
    Used for pool-based success-counting systems (World of Darkness, Year Zero).
    """
    if not isinstance(pool, list):
        raise ValueError("count_successes(): first argument must be a list")
    if not isinstance(threshold, int):
        raise ValueError("count_successes(): threshold must be an int")
    return sum(1 for die in pool if die >= threshold)


def _safe_explode(pool: List[int], sides: int, on: int | None = None, max_explosions: int = 10) -> List[int]:
    """Re-roll dice that land on the explode value (default: sides) and add new results.

    Each die that lands on the explode value is kept AND an additional die is rolled.
    The new die can also explode, up to max_explosions total extra rolls.
    """
    if not isinstance(pool, list):
        raise ValueError("explode(): pool must be a list")
    explode_on = on if on is not None else sides
    if not isinstance(explode_on, int) or explode_on < 1 or explode_on > sides:
        raise ValueError(f"explode(): on value {explode_on!r} must be between 1 and {sides}")
    result = list(pool)
    extra_rolls = 0
    i = 0
    while i < len(result) and extra_rolls < max_explosions:
        if result[i] == explode_on:
            new_die = random.randint(1, sides)
            result.append(new_die)
            extra_rolls += 1
        i += 1
    return result


def _safe_roll_fudge(n: int) -> List[int]:
    """Roll n FATE/Fudge dice. Each die returns -1, 0, or 1 with equal probability.

    Example: roll_fudge(4) might return [-1, 0, 1, 1].
    Sum the result for the final FATE roll: sum(roll_fudge(4)).
    """
    if not isinstance(n, int) or n < 1:
        raise ValueError(f"roll_fudge(): n must be a positive int, got {n!r}")
    return [random.choice([-1, 0, 1]) for _ in range(n)]


def _safe_weighted_roll(options: List[Any], weights: List[int | float]) -> Any:  # noqa: ANN401
    """Return one element from options selected by the given weights.

    Example: weighted_roll(['miss', 'hit', 'crit'], [50, 40, 10]).
    Unlike choice() which assumes equal probability, this accepts explicit weights.
    """
    if not isinstance(options, list) or not isinstance(weights, list):
        raise ValueError("weighted_roll(): both arguments must be lists")
    if not options:
        raise ValueError("weighted_roll(): options list must not be empty")
    if len(options) != len(weights):
        raise ValueError(f"weighted_roll(): options length {len(options)} != weights length {len(weights)}")
    return random.choices(options, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Die shorthand aliases
# ---------------------------------------------------------------------------


# Ergonomic aliases for the most common die types. Naming matches universal TTRPG shorthand.
def _d4() -> int:
    return random.randint(1, 4)


def _d6() -> int:
    return random.randint(1, 6)


def _d8() -> int:
    return random.randint(1, 8)


def _d10() -> int:
    return random.randint(1, 10)


def _d12() -> int:
    return random.randint(1, 12)


def _d20() -> int:
    return random.randint(1, 20)


def _d100() -> int:
    return random.randint(1, 100)


# ---------------------------------------------------------------------------
# Display and numeric helpers
# ---------------------------------------------------------------------------


def _ordinal(n: int) -> str:
    """Return the ordinal string representation of n.

    Examples: ordinal(1) → '1st', ordinal(2) → '2nd', ordinal(13) → '13th'.
    Teen numbers (11th, 12th, 13th) always use 'th'.
    """
    if not isinstance(n, int):
        raise ValueError(f"ordinal(): argument must be an int, got {type(n).__name__}")
    # Special cases for 11th, 12th, 13th (teen numbers always use 'th').
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _signed(n: int | float) -> str:
    """Return n as a signed string: +3, -2, 0.

    Useful for narrative stat-change display: 'You gained {{ signed(amount) }} strength.'
    """
    if not isinstance(n, (int, float)):
        raise ValueError(f"signed(): argument must be numeric, got {type(n).__name__}")
    return f"+{n}" if n > 0 else str(n)


def _stat_mod(value: int) -> int:
    """Return the D&D-style ability score modifier: floor((value - 10) / 2).

    Example: stat_mod(14) → 2, stat_mod(8) → -1, stat_mod(10) → 0.
    Available as a function in addition to the existing | stat_modifier filter,
    for use in formula expressions: roll(1, 20) + stat_mod(player.stats[\"strength\"]).
    """
    if not isinstance(value, int):
        raise ValueError(f"stat_mod(): argument must be an int, got {type(value).__name__}")
    return (value - 10) // 2


# ---------------------------------------------------------------------------
# Combat formula dice helpers (single-call convenience wrappers)
# ---------------------------------------------------------------------------


def _rollpool(n: int, sides: int, threshold: int) -> int:
    """Roll n dice of ``sides`` sides and return the count of dice whose result is >= threshold.

    Raises ValueError on invalid inputs (n < 1, sides < 2, threshold < 1).
    """
    if n < 1:
        raise ValueError(f"rollpool(): n must be >= 1, got {n}")
    if sides < 2:
        raise ValueError(f"rollpool(): sides must be >= 2, got {sides}")
    if threshold < 1:
        raise ValueError(f"rollpool(): threshold must be >= 1, got {threshold}")
    return sum(1 for _ in range(n) if random.randint(1, sides) >= threshold)


def _rollsum(n: int, sides: int) -> int:
    """Roll n dice of ``sides`` sides and return their sum.

    Raises ValueError on invalid inputs (n < 1, sides < 2).
    """
    if n < 1:
        raise ValueError(f"rollsum(): n must be >= 1, got {n}")
    if sides < 2:
        raise ValueError(f"rollsum(): sides must be >= 2, got {sides}")
    return sum(random.randint(1, sides) for _ in range(n))


def _keephigh(n: int, sides: int, k: int) -> int:
    """Roll n dice of ``sides`` sides and return the sum of the highest k.

    Raises ValueError when k > n or other invalid inputs (n < 1, sides < 2, k < 1).
    """
    if n < 1:
        raise ValueError(f"keephigh(): n must be >= 1, got {n}")
    if sides < 2:
        raise ValueError(f"keephigh(): sides must be >= 2, got {sides}")
    if k < 1:
        raise ValueError(f"keephigh(): k must be >= 1, got {k}")
    if k > n:
        raise ValueError(f"keephigh(): k={k} exceeds n={n}")
    rolls = sorted((random.randint(1, sides) for _ in range(n)), reverse=True)
    return sum(rolls[:k])


SAFE_GLOBALS: Dict[str, Any] = {
    "roll": _safe_roll,
    "choice": _safe_choice,
    "random": _safe_random,
    "sample": _safe_sample,
    "now": _now,
    "today": _today,
    "clamp": _clamp,
    "max": max,
    "min": min,
    "round": round,
    "sum": sum,
    "floor": math.floor,
    "ceil": math.ceil,
    "abs": abs,
    "range": range,
    "len": len,
    "int": int,
    "str": str,
    "bool": bool,
    # Calendar and astronomical utilities — see oscilla/engine/calendar_utils.py.
    # Factored into a shared module so the future condition evaluator can import
    # the same functions without duplicating logic.
    "season": calendar_utils.season,
    "month_name": calendar_utils.month_name,
    "day_name": calendar_utils.day_name,
    "week_number": calendar_utils.week_number,
    "mean": calendar_utils.mean,
    "zodiac_sign": calendar_utils.zodiac_sign,
    "chinese_zodiac": calendar_utils.chinese_zodiac,
    "moon_phase": calendar_utils.moon_phase,
    # Time constants for cooldown expressions.
    "SECONDS_PER_MINUTE": SECONDS_PER_MINUTE,
    "SECONDS_PER_HOUR": SECONDS_PER_HOUR,
    "SECONDS_PER_DAY": SECONDS_PER_DAY,
    "SECONDS_PER_WEEK": SECONDS_PER_WEEK,
    # Dice pools
    "roll_pool": _safe_roll_pool,
    "keep_highest": _safe_keep_highest,
    "keep_lowest": _safe_keep_lowest,
    "count_successes": _safe_count_successes,
    "explode": _safe_explode,
    "roll_fudge": _safe_roll_fudge,
    "weighted_roll": _safe_weighted_roll,
    # Combat formula helpers (single-call convenience wrappers)
    "rollpool": _rollpool,
    "rollsum": _rollsum,
    "keephigh": _keephigh,
    # Die shorthand aliases
    "d4": _d4,
    "d6": _d6,
    "d8": _d8,
    "d10": _d10,
    "d12": _d12,
    "d20": _d20,
    "d100": _d100,
    # Display and numeric helpers
    "ordinal": _ordinal,
    "signed": _signed,
    "stat_mod": _stat_mod,
}


# ---------------------------------------------------------------------------
# Built-in template filters
# ---------------------------------------------------------------------------


def _filter_stat_modifier(stat_value: int) -> str:
    """Convert integer stat to a signed modifier string (D&D-style)."""
    modifier = (stat_value - 10) // 2
    return f"+{modifier}" if modifier >= 0 else str(modifier)


def _filter_pluralize(count: int, singular: str, plural: str | None = None) -> str:
    """Return singular or plural form based on count."""
    if count == 1:
        return singular
    return plural if plural is not None else f"{singular}s"


SAFE_FILTERS: Dict[str, Callable[..., Any]] = {
    "stat_modifier": _filter_stat_modifier,
    "pluralize": _filter_pluralize,
}


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class TemplateValidationError(Exception):
    """Raised during mock-render when a template accesses an invalid context property."""


class TemplateRuntimeError(RuntimeError):
    """Raised when a precompiled template fails at runtime."""


# ---------------------------------------------------------------------------
# Mock context for load-time validation
# ---------------------------------------------------------------------------


class _StrictMockDict:
    """Dict-like object that raises TemplateValidationError on missing keys."""

    def __init__(self, data: Dict[str, Any], label: str) -> None:
        self._data = data
        self._label = label

    def __getitem__(self, key: str) -> Any:
        if key not in self._data:
            raise TemplateValidationError(f"{self._label}[{key!r}] does not exist")
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class _MockPlayerMilestones:
    def has(self, name: str) -> bool:
        # Always return True so {% if player.milestones.has('x') %} branches are exercised.
        return True

    def __getattr__(self, name: str) -> Any:
        raise TemplateValidationError(f"player.milestones has no attribute {name!r}")


@dataclass
class _MockPlayerPronouns:
    subject: str = "they"
    object: str = "them"
    possessive: str = "their"
    possessive_standalone: str = "theirs"
    reflexive: str = "themselves"
    uses_plural_verbs: bool = True

    def __getattr__(self, name: str) -> Any:
        raise TemplateValidationError(f"player.pronouns has no attribute {name!r}")


class _MockPlayer:
    """Mock PlayerContext for load-time validation.

    All valid properties return sensible mock values. Any unrecognised attribute
    access raises TemplateValidationError, which is surfaced as a load error.
    """

    def __init__(self, stat_names: List[str]) -> None:
        self.name = "TestPlayer"
        self.prestige_count = 0
        self.milestones = _MockPlayerMilestones()
        self.pronouns = _MockPlayerPronouns()
        # Build stats dict from CharacterConfig stat names with mock values.
        self.stats = _StrictMockDict(
            {name: 10 for name in stat_names},
            label="player.stats",
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Convenience shorthand for player.stats.get(key, default) — mirrors PlayerContext.get()."""
        return self.stats.get(key, default)

    def __getattr__(self, name: str) -> Any:
        raise TemplateValidationError(f"player has no attribute {name!r}")


class _MockCombatContext:
    enemy_stats: Dict[str, int] = field(default_factory=dict)
    enemy_name: str = "Test Enemy"
    turn: int = 1
    combat_stats: Dict[str, int] = field(default_factory=dict)

    def __init__(self) -> None:
        self.enemy_stats = {}
        self.combat_stats = {}

    def __getattr__(self, name: str) -> Any:
        raise TemplateValidationError(f"combat has no attribute {name!r}")


class _MockGame:
    """Mock GameContext for load-time template validation."""

    season_hemisphere: str = "northern"
    timezone: str | None = None

    def __getattr__(self, name: str) -> Any:
        raise TemplateValidationError(f"game has no attribute {name!r}")


class _MockInGameCycles:
    """Mock cycle dict for load-time template validation of ingame_time.cycles[x]."""

    def __init__(self, default_cycle: Any) -> None:
        self._default = default_cycle

    def __getitem__(self, key: str) -> Any:
        return self._default

    def get(self, key: str, default: Any = None) -> Any:
        return self._default


class _MockInGameEras:
    """Mock era dict for load-time template validation of ingame_time.eras[x]."""

    def __init__(self, default_era: Any) -> None:
        self._default = default_era

    def __getitem__(self, key: str) -> Any:
        return self._default

    def get(self, key: str, default: Any = None) -> Any:
        return self._default


def build_mock_context(
    stat_names: List[str],
    include_combat: bool = False,
    has_ingame_time: bool = False,
    manifest_properties: Dict[str, int | float | str | bool] | None = None,
) -> Dict[str, Any]:
    """Build a comprehensive mock context for load-time template validation."""
    ctx: Dict[str, Any] = {}
    ctx.update(SAFE_GLOBALS)
    ctx["player"] = _MockPlayer(stat_names)
    # Use a single _MockGame instance for both ctx["game"] and the season() closure
    # so they share the same object rather than creating two separate instances.
    mock_game = _MockGame()
    ctx["game"] = mock_game
    # Expose manifest properties as `this` for template validation.
    ctx["this"] = manifest_properties if manifest_properties is not None else {}
    if include_combat:
        mock_combat = _MockCombatContext()
        ctx["combat"] = mock_combat
        # Also expose top-level aliases so skill use_effects templates can use
        # enemy_stats/combat_stats/turn_number directly, consistent with
        # CombatFormulaContext (used in player_damage_formulas).
        ctx["enemy_stats"] = mock_combat.enemy_stats
        ctx["combat_stats"] = mock_combat.combat_stats
        ctx["turn_number"] = mock_combat.turn
    # Override the season function with a closure that respects mock hemisphere.
    ctx["season"] = lambda date: calendar_utils.season(date, hemisphere=mock_game.season_hemisphere)
    ctx["today"] = lambda: datetime.date.today()
    ctx["now"] = lambda: datetime.datetime.now()
    if has_ingame_time:
        # Provide a minimal mock InGameTimeView so templates referencing
        # ingame_time at load time pass the semantic check.
        from typing import cast as _cast

        from oscilla.engine.ingame_time import CycleState, EraState, InGameTimeView

        mock_cycle = CycleState(name="mock", position=0, label="Mock")
        mock_era = EraState(name="mock", count=1, active=True)
        ctx["ingame_time"] = InGameTimeView(
            internal_ticks=0,
            game_ticks=0,
            cycles=_cast(Dict[str, CycleState], _MockInGameCycles(mock_cycle)),
            eras=_cast(Dict[str, EraState], _MockInGameEras(mock_era)),
        )
    return ctx


# ---------------------------------------------------------------------------
# Template engine
# ---------------------------------------------------------------------------


class GameTemplateEngine:
    """Sandboxed Jinja2 template engine for content manifests.

    Templates are precompiled at load time via precompile_and_validate() and
    rendered at runtime via render() or render_int(). The engine is stored on
    ContentRegistry and threaded through the pipeline at runtime.
    """

    def __init__(self, stat_names: List[str], has_ingame_time: bool = False) -> None:
        self._stat_names = stat_names
        self._has_ingame_time = has_ingame_time
        from jinja2 import StrictUndefined

        self._env = SandboxedEnvironment(undefined=StrictUndefined)
        self._env.globals.update(SAFE_GLOBALS)
        self._env.filters.update(SAFE_FILTERS)
        # template_id → compiled Jinja2 Template
        self._cache: Dict[str, Any] = {}

    def precompile_and_validate(
        self,
        raw: str,
        template_id: str,
        context_type: str,
        manifest_properties: Dict[str, int | float | str | bool] | None = None,
    ) -> None:
        """Preprocess, compile, and mock-render a template string.

        Raises TemplateValidationError on any failure. Called from loader.py
        so errors become ContentLoadErrors before the registry is built.

        context_type is one of: 'adventure', 'combat', 'effect'
        manifest_properties is the current manifest's properties dict for `this` context.
        """
        # Step 1: pronoun preprocessing
        processed = preprocess_pronouns(raw)

        # Step 2: Jinja2 compilation (syntax check)
        try:
            template = self._env.from_string(processed)
        except TemplateError as exc:
            raise TemplateValidationError(f"Syntax error in template {template_id!r}: {exc}") from exc

        # Step 3: mock render (semantic / access check)
        include_combat = context_type == "combat"
        mock_ctx = build_mock_context(
            self._stat_names,
            include_combat=include_combat,
            has_ingame_time=self._has_ingame_time,
            manifest_properties=manifest_properties,
        )
        try:
            template.render(**mock_ctx)
        except TemplateValidationError:
            raise  # already has a good message
        except Exception as exc:
            raise TemplateValidationError(f"Template {template_id!r} failed mock render: {exc}") from exc

        # Step 4: cache the compiled template
        self._cache[template_id] = template

    def render(self, template_id: str, ctx: ExpressionContext) -> str:
        """Render a precompiled template with a live ExpressionContext.

        Raises TemplateRuntimeError if anything goes wrong.
        """
        template = self._cache.get(template_id)
        if template is None:
            raise TemplateRuntimeError(f"Template {template_id!r} not found in cache — was it precompiled?")
        render_ctx: Dict[str, Any] = {}
        render_ctx.update(SAFE_GLOBALS)
        render_ctx["player"] = ctx.player
        render_ctx["combat"] = ctx.combat
        render_ctx["game"] = ctx.game
        render_ctx["this"] = ctx.this
        # When a CombatContextView is present, also expose its fields at the top level
        # (enemy_stats, combat_stats, turn_number) so that skill use_effects templates
        # can use the same variable names as player_damage_formulas in CombatFormulaContext.
        if ctx.combat is not None:
            render_ctx["enemy_stats"] = ctx.combat.enemy_stats
            render_ctx["combat_stats"] = ctx.combat.combat_stats
            render_ctx["turn_number"] = ctx.combat.turn
        # Override time functions from SAFE_GLOBALS with closures that respect
        # the game's configured timezone. today() and now() return values in the
        # game's timezone; season() uses the hemisphere from that same context.
        resolved_dt = calendar_utils.resolve_local_datetime(ctx.game.timezone)
        tz = resolved_dt.tzinfo
        render_ctx["today"] = lambda: datetime.datetime.now(tz=tz).date()
        render_ctx["now"] = lambda: datetime.datetime.now(tz=tz)
        render_ctx["season"] = lambda date: calendar_utils.season(date, hemisphere=ctx.game.season_hemisphere)
        try:
            return str(template.render(**render_ctx))
        except Exception as exc:
            raise TemplateRuntimeError(f"Template {template_id!r} failed at runtime: {exc}") from exc

    def render_int(self, template_id: str, ctx: ExpressionContext) -> int:
        """Render a template that must produce an integer value."""
        result = self.render(template_id, ctx).strip()
        try:
            return int(result)
        except ValueError:
            raise TemplateRuntimeError(f"Template {template_id!r} produced {result!r} — expected an integer")

    def is_template(self, value: str) -> bool:
        """Return True if value looks like a Jinja2 template string."""
        return "{{" in value or "{%" in value or bool(re.search(r"\{[A-Za-z]+\}", value))

    def render_raw(self, raw: str) -> str:
        """Render an ad-hoc template string using only SAFE_GLOBALS.

        Intended for cooldown field expressions (e.g. ``"{{ SECONDS_PER_DAY }}"``) that
        require no player or combat context — only the injected constants.
        Raises TemplateRuntimeError on failure.
        """
        try:
            template = self._env.from_string(raw)
            return str(template.render(**SAFE_GLOBALS))
        except Exception as exc:
            raise TemplateRuntimeError(f"Failed to render raw template {raw!r}: {exc}") from exc

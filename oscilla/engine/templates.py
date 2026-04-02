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
    """Read-only milestone set exposed to templates as player.milestones."""

    _milestones: Set[str] = field(default_factory=set)

    def has(self, name: str) -> bool:
        return name in self._milestones


@dataclass(frozen=True)
class PlayerContext:
    """Read-only projection of CharacterState for template rendering.

    Exposing only safe scalar fields and view objects prevents templates from
    accidentally (or deliberately) mutating game state.
    """

    name: str
    level: int
    iteration: int
    hp: int
    max_hp: int
    stats: Dict[str, int | bool | None]
    milestones: PlayerMilestoneView
    pronouns: PlayerPronounView

    @classmethod
    def from_character(cls, char: "CharacterState") -> "PlayerContext":
        return cls(
            name=char.name,
            level=char.level,
            iteration=char.iteration,
            hp=char.hp,
            max_hp=char.max_hp,
            stats=dict(char.stats),
            milestones=PlayerMilestoneView(_milestones=set(char.milestones)),
            pronouns=PlayerPronounView.from_set(char.pronouns),
        )


@dataclass(frozen=True)
class CombatContextView:
    """Read-only combat state exposed to templates as combat.

    Only present when a template is rendered inside a CombatStep handler.
    """

    enemy_hp: int
    enemy_name: str
    turn: int


@dataclass
class ExpressionContext:
    """Complete read-only context passed to every template render call.

    combat is None for non-combat steps. Templates that reference combat.*
    will raise UndefinedError at mock-render time if the context_type is not
    'combat', which is caught as a validation error at load time.
    """

    player: PlayerContext
    combat: CombatContextView | None = None


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
        self.level = 5
        self.iteration = 0
        self.hp = 30
        self.max_hp = 30
        self.milestones = _MockPlayerMilestones()
        self.pronouns = _MockPlayerPronouns()
        # Build stats dict from CharacterConfig stat names with mock values.
        self.stats = _StrictMockDict(
            {name: 10 for name in stat_names},
            label="player.stats",
        )

    def __getattr__(self, name: str) -> Any:
        raise TemplateValidationError(f"player has no attribute {name!r}")


class _MockCombatContext:
    enemy_hp: int = 20
    enemy_name: str = "Test Enemy"
    turn: int = 1

    def __getattr__(self, name: str) -> Any:
        raise TemplateValidationError(f"combat has no attribute {name!r}")


def build_mock_context(stat_names: List[str], include_combat: bool = False) -> Dict[str, Any]:
    """Build a comprehensive mock context for load-time template validation."""
    ctx: Dict[str, Any] = {"player": _MockPlayer(stat_names)}
    if include_combat:
        ctx["combat"] = _MockCombatContext()
    ctx.update(SAFE_GLOBALS)
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

    def __init__(self, stat_names: List[str]) -> None:
        self._stat_names = stat_names
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
    ) -> None:
        """Preprocess, compile, and mock-render a template string.

        Raises TemplateValidationError on any failure. Called from loader.py
        so errors become ContentLoadErrors before the registry is built.

        context_type is one of: 'adventure', 'combat', 'effect'
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
        mock_ctx = build_mock_context(self._stat_names, include_combat=include_combat)
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
        render_ctx: Dict[str, Any] = {
            "player": ctx.player,
            "combat": ctx.combat,
        }
        render_ctx.update(SAFE_GLOBALS)
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

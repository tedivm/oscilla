# Design: Calendar Conditions

## Context

The condition evaluator is the engine's universal gate — any content decision that depends on character or world state should flow through it. This is one of the system's core design principles.

`oscilla/engine/calendar_utils.py` already implements all required calendar logic — `season()`, `moon_phase()`, `zodiac_sign()`, `chinese_zodiac()`, and helpers — as pure functions with no external dependencies. The module docstring explicitly states it was factored out _"so the future condition evaluator can import the same functions without duplication."_ That future is now.

The template engine already exposes every calendar function to Jinja2 templates, so authors can vary narrative text based on the calendar. What is missing is the ability to gate entire adventures, branches, or effects on calendar state. This change adds that capability by adding 8 new condition leaf predicates to `models/base.py` and the corresponding `case` branches to `conditions.py`.

A secondary capability is added alongside: making game configuration available inside templates. Currently `ExpressionContext` carries only `player` and `combat`. The `game` object — specifically `GameSpec.season_hemisphere` — is needed by the template `season()` function to produce hemisphere-correct results without requiring authors to pass the hemisphere explicitly. Exposing a `GameContext` projection inside `ExpressionContext` solves this cleanly and opens the door to other game-config template access in future changes.

**Current state before this change:**

| Gap                              | Detail                                                                                    |
| -------------------------------- | ----------------------------------------------------------------------------------------- |
| No calendar conditions           | Authors can use `season()` in text templates but cannot gate adventure availability on it |
| `season_is` hemispheres          | `season()` is hardcoded Northern Hemisphere in both `calendar_utils` and template engine  |
| Templates have no `game` context | `ExpressionContext` only exposes `player` and `combat`                                    |

---

## Goals / Non-Goals

**Goals:**

- Add 8 calendar condition predicates to the condition evaluator: `season_is`, `moon_phase_is`, `zodiac_is`, `chinese_zodiac_is`, `month_is`, `day_of_week_is`, `date_is`, `time_between`
- Accept month and day-of-week values as either integers or English strings (e.g. `"October"` or `10`)
- `date_is` supports optional `year` for one-off dated events
- `time_between` handles midnight-wrapping ranges (e.g. `22:00`–`04:00`)
- Add `season_hemisphere: northern | southern` to `GameSpec`; `season_is` and the template `season()` function both respect it
- Expose a read-only `GameContext` object in `ExpressionContext` so templates can access game-level configuration
- Update `condition-evaluator` and `dynamic-content-templates` specs
- Add `docs/authors/calendar-conditions.md`
- Add testlandia content exercising all new predicates

**Non-Goals:**

- In-game time system (a separate roadmap item requiring player state, DB migration, and tick events)
- Astronomical precision or real-time clock beyond `datetime.date.today()` and `datetime.datetime.now()`
- Any TUI changes
- Any database migrations

---

## Decisions

### Decision 1 — `month_is` and `day_of_week_is` accept string or integer

**Decision**: Both accept `int | str` in the Pydantic model. A `@model_validator` normalizes strings to integers at parse time, so the condition evaluator always receives and compares integers.

**Rationale**: Authoring with `"October"` is more readable and less error-prone than `10`. Normalizing at parse time keeps the evaluator simple, validates input early, and ensures consistent behavior regardless of input form.

**Alternative considered**: Accept only integers. Rejected — adds friction for authors with no implementation benefit.

String normalisation:

- Month names: `calendar.month_name` (case-insensitive, full name only — not abbreviations)
- Weekday names: `calendar.day_name` (case-insensitive, full name only — not abbreviations)

### Decision 2 — `date_is` matches on month+day+optional year

**Decision**: `DateIsCondition` has fields `month: int | str`, `day: int`, and `year: int | None = None`. When `year` is omitted (or `None`), the condition matches any year. When `year` is present, it matches only that specific calendar year.

**Rationale**: Supports both recurrent annual events (Christmas = month 12, day 25) and one-off dates (a real-world launch date or community event).

### Decision 3 — `time_between` uses 24-hour HH:MM format, not AM/PM

**Decision**: The `start` and `end` values for `time_between` SHALL be strings in 24-hour `HH:MM` format (e.g. `"22:00"`, `"09:30"`). AM/PM notation is explicitly not supported. The Pydantic model enforces this with a `pattern=r"^\d{2}:\d{2}$"` field validator, so any value that does not match the two-digit-colon-two-digit shape is rejected at content load time.

**Rationale**: 24-hour format is unambiguous — there is no `12:00 AM` vs `12:00 PM` edge case — and is the standard convention for machine-readable time values. AM/PM parsing introduces locale and ambiguity concerns (is `12:00 PM` noon or midnight?) that add complexity and confusion for no authoring benefit. Authors already writing hours as `22:00` (the most natural "night" example) are already using 24-hour notation intuitively.

### Decision 4 — `time_between` wraps midnight

**Decision**: When `start` (HH:MM) is numerically greater than `end`, the condition is interpreted as spanning midnight. This means it evaluates to true when `now_time >= start OR now_time <= end`. When `start <= end`, it is a same-day window, true only when `start <= now_time <= end`.

**Rationale**: Authors writing a "night-time" condition naturally write `start: "22:00", end: "06:00"`. Requiring them to express this as an `any` of two ranges would be a worse authoring experience.

**Edge case**: `start == end` (e.g. both `"12:00"`) — evaluates to false, since the window has zero duration. This is logged at warning level.

### Decision 5 — `season_is` reads hemisphere from registry; templates get `GameContext`

**Decision**: `season_is` reads `registry.game.spec.season_hemisphere` when a registry is available. When `registry` is `None`, it defaults to `"northern"` with a `logger.warning`. The `ExpressionContext` gains a `game: GameContext` field (default `GameContext(season_hemisphere="northern")`), and the template `season()` function is overridden per-render with a closure that captures the hemisphere from `ctx.game`.

**Rationale**: Authors should not need to pass `hemisphere` as an argument to `season()` in templates — that would expose an implementation detail and require every template using `season()` to be updated if the game changes hemisphere. The closure approach in `render()` makes it transparent. The default value on `ExpressionContext` ensures all existing tests that create contexts without game data continue to work unchanged.

**Callers updated**: `pipeline.py` `_build_context()` and the fallback `ExpressionContext` construction in `effects.py` `run_effect()`.

### Decision 6 — `chinese_zodiac_is` is included

The `chinese_zodiac()` function is already in `calendar_utils.py`. Including it as a condition predicate is a one-line addition with no coupling cost and makes the predicate set consistent with what templates expose.

### Decision 7 — `timezone` in `GameSpec` controls the clock for `time_between`; absent falls back to server local

**Decision**: `GameSpec` gains an optional `timezone: str | None = None` field accepting an IANA timezone name (e.g. `"America/New_York"`, `"Europe/London"`). When set, **all calendar predicates** derive the current date and time from `datetime.datetime.now(tz=zoneinfo.ZoneInfo(timezone))`. When the field is absent or `None`, `datetime.datetime.now()` is used (server local time). If the value is set but the IANA key is unrecognized by `zoneinfo`, a `logger.warning` is emitted and evaluation falls back to server local time without raising an error.

**Rationale**: Seasons, zodiac signs, moon phases, months, weekdays, and dates all change at midnight — but midnight is different everywhere. A game authored for a specific audience region (e.g. a Japanese game assuming JST) should see the correct season, weekday, and date for that region regardless of server location. Scoping the timezone only to `time_between` would create subtle inconsistencies where `time_between: {start: "00:00", end: "06:00"}` could be true while `day_of_week_is: Tuesday` is still reading the previous day. A single `_current_datetime()` helper called once per evaluation resolves this uniformly. `zoneinfo` is stdlib in Python 3.9+ (the project targets 3.12+), so no extra dependency is introduced.

---

## Implementation

### File: `oscilla/engine/calendar_utils.py`

Add `hemisphere` parameter to `season()`:

**Before:**

```python
def season(date: datetime.date) -> str:
    """Return the meteorological season for the given date.

    Returns one of: "spring", "summer", "autumn", "winter".
    """
    m = date.month
    for start, end, name in _SEASON_MONTHS:
        if start <= m <= end:
            return name
    return "winter"  # unreachable; satisfies type checker
```

**After:**

```python
# Northern Hemisphere meteorological seasons.
_SEASON_MONTHS_N: tuple[tuple[int, int, str], ...] = (
    (3, 5, "spring"),
    (6, 8, "summer"),
    (9, 11, "autumn"),
    (12, 12, "winter"),
    (1, 2, "winter"),
)

# Southern Hemisphere — spring and autumn swap, summer and winter swap.
_SEASON_MONTHS_S: tuple[tuple[int, int, str], ...] = (
    (3, 5, "autumn"),
    (6, 8, "winter"),
    (9, 11, "spring"),
    (12, 12, "summer"),
    (1, 2, "summer"),
)


def season(date: datetime.date, hemisphere: str = "northern") -> str:
    """Return the meteorological season for the given date.

    Returns one of: "spring", "summer", "autumn", "winter".

    hemisphere: "northern" (default) or "southern". Southern Hemisphere
    reverses the thermal seasons, so December is summer not winter.
    """
    table = _SEASON_MONTHS_S if hemisphere == "southern" else _SEASON_MONTHS_N
    m = date.month
    for start, end, name in table:
        if start <= m <= end:
            return name
    return "winter"  # unreachable; satisfies type checker
```

Remove the old `_SEASON_MONTHS` constant (replaced by the two named tables above).

Also add a new public helper used by both the condition evaluator and the template engine:

```python
def resolve_local_datetime(timezone_name: str | None) -> datetime.datetime:
    """Return the current datetime in the given IANA timezone.

    Falls back to server local time when timezone_name is None or when
    the key is not recognised by zoneinfo. Unrecognised keys emit a warning.
    """
    if timezone_name is not None:
        try:
            return datetime.datetime.now(tz=zoneinfo.ZoneInfo(timezone_name))
        except zoneinfo.ZoneInfoNotFoundError:
            logger.warning(
                "Unknown timezone %r in game config; falling back to server local time.",
                timezone_name,
            )
    return datetime.datetime.now()
```

Add `import zoneinfo` and import the logger at the top of `calendar_utils.py`:

```python
import zoneinfo
from logging import getLogger

logger = getLogger(__name__)
```

This centralises the timezone-resolution logic so neither `conditions.py` nor `templates.py` needs to duplicate the `ZoneInfoNotFoundError` guard.

### File: `oscilla/engine/models/game.py`

Add `season_hemisphere` to `GameSpec`:

**Before:**

```python
class GameSpec(BaseModel):
    displayName: str
    description: str = ""
    xp_thresholds: List[int] = Field(min_length=1)
    hp_formula: HpFormula
    item_labels: List[ItemLabelDef] = []
    passive_effects: List[PassiveEffect] = []
    outcomes: List[str] = Field(default_factory=list)
```

**After:**

```python
class GameSpec(BaseModel):
    displayName: str
    description: str = ""
    xp_thresholds: List[int] = Field(min_length=1)
    hp_formula: HpFormula
    item_labels: List[ItemLabelDef] = []
    passive_effects: List[PassiveEffect] = []
    outcomes: List[str] = Field(default_factory=list)
    # Hemisphere used by season() to compute meteorological seasons.
    # "northern" (default) or "southern". Only affects season(); all other
    # calendar functions are hemisphere-agnostic.
    season_hemisphere: Literal["northern", "southern"] = "northern"
    # IANA timezone name (e.g. "America/New_York") used by time_between.
    # Defaults to None (server local time).
    timezone: str | None = None
```

Also add `Literal` to the import:

```python
from typing import List, Literal
```

---

### File: `oscilla/engine/models/base.py`

Add 8 new condition model classes and register them in the `Condition` union.

**New classes to add** (insert before the branch node classes):

```python
import calendar as _calendar_module  # stdlib, avoid shadowing local variable names


def _resolve_month(value: int | str) -> int:
    """Normalise a month value to an integer 1-12.

    Accepts int (1-12) or full English month name (case-insensitive).
    Raises ValueError for unrecognised values.
    """
    if isinstance(value, int):
        if not (1 <= value <= 12):
            raise ValueError(f"month must be 1-12, got {value}")
        return value
    # Find month by full name comparison (case-insensitive).
    # calendar.month_name is 1-indexed; index 0 is the empty string.
    for i in range(1, 13):
        if _calendar_module.month_name[i].lower() == value.lower():
            return i
    raise ValueError(f"Unrecognised month name: {value!r}")


def _resolve_weekday(value: int | str) -> int:
    """Normalise a day-of-week value to an integer 0-6 (Monday=0, Sunday=6).

    Accepts int (0-6) or full English weekday name (case-insensitive).
    Raises ValueError for unrecognised values.
    """
    if isinstance(value, int):
        if not (0 <= value <= 6):
            raise ValueError(f"day_of_week must be 0-6, got {value}")
        return value
    for i in range(7):
        if _calendar_module.day_name[i].lower() == value.lower():
            return i
    raise ValueError(f"Unrecognised weekday name: {value!r}")


class SeasonIsCondition(BaseModel):
    type: Literal["season_is"]
    value: Literal["spring", "summer", "autumn", "winter"]


class MoonPhaseIsCondition(BaseModel):
    type: Literal["moon_phase_is"]
    value: Literal[
        "New Moon",
        "Waxing Crescent",
        "First Quarter",
        "Waxing Gibbous",
        "Full Moon",
        "Waning Gibbous",
        "Last Quarter",
        "Waning Crescent",
    ]


class ZodiacIsCondition(BaseModel):
    type: Literal["zodiac_is"]
    value: Literal[
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]


class ChineseZodiacIsCondition(BaseModel):
    type: Literal["chinese_zodiac_is"]
    value: Literal[
        "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
        "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig",
    ]


class MonthIsCondition(BaseModel):
    """True when today's month matches the given value.

    Accepts an integer (1-12) or a full English month name ("January"..."December").
    Normalised to int by model validator.
    """
    type: Literal["month_is"]
    value: int | str

    @model_validator(mode="after")
    def normalise_month(self) -> "MonthIsCondition":
        object.__setattr__(self, "value", _resolve_month(self.value))
        return self


class DayOfWeekIsCondition(BaseModel):
    """True when today's weekday matches the given value.

    Accepts an integer (0=Monday ... 6=Sunday) or a full English name.
    Normalised to int by model validator.
    """
    type: Literal["day_of_week_is"]
    value: int | str

    @model_validator(mode="after")
    def normalise_weekday(self) -> "DayOfWeekIsCondition":
        object.__setattr__(self, "value", _resolve_weekday(self.value))
        return self


class DateIsCondition(BaseModel):
    """True when today matches the given month/day, and optionally year.

    When year is omitted the condition matches annually on that date.
    When year is present it matches only on that specific calendar date.
    month accepts int (1-12) or full English name; day is always int.
    """
    type: Literal["date_is"]
    month: int | str
    day: int = Field(ge=1, le=31)
    year: int | None = None

    @model_validator(mode="after")
    def normalise_month(self) -> "DateIsCondition":
        object.__setattr__(self, "month", _resolve_month(self.month))
        return self


class TimeBetweenCondition(BaseModel):
    """True when the current local time falls in the window [start, end].

    Both values are HH:MM strings in 24-hour format.
    When start > end the window wraps midnight (e.g. 22:00–04:00 is "night").
    When start == end the window has zero duration and always evaluates False.
    """
    type: Literal["time_between"]
    start: str = Field(pattern=r"^\d{2}:\d{2}$", description="HH:MM (24-hour)")
    end: str = Field(pattern=r"^\d{2}:\d{2}$", description="HH:MM (24-hour)")
```

**Updated `Condition` union** (after = add the 8 new types):

```python
Condition = Annotated[
    Union[
        AllCondition,
        AnyCondition,
        NotCondition,
        LevelCondition,
        MilestoneCondition,
        ItemCondition,
        ItemEquippedCondition,
        ItemHeldLabelCondition,
        AnyItemEquippedCondition,
        CharacterStatCondition,
        PrestigeCountCondition,
        ClassCondition,
        EnemiesDefeatedCondition,
        LocationsVisitedCondition,
        AdventuresCompletedCondition,
        SkillCondition,
        PronounsCondition,
        QuestStageCondition,
        # Calendar predicates
        SeasonIsCondition,
        MoonPhaseIsCondition,
        ZodiacIsCondition,
        ChineseZodiacIsCondition,
        MonthIsCondition,
        DayOfWeekIsCondition,
        DateIsCondition,
        TimeBetweenCondition,
    ],
    Field(discriminator="type"),
]
```

---

### File: `oscilla/engine/conditions.py`

**Before — imports:**

```python
from oscilla.engine.models.base import (
    AdventuresCompletedCondition,
    AllCondition,
    AnyCondition,
    AnyItemEquippedCondition,
    CharacterStatCondition,
    ClassCondition,
    Condition,
    EnemiesDefeatedCondition,
    ItemCondition,
    ItemEquippedCondition,
    ItemHeldLabelCondition,
    LevelCondition,
    LocationsVisitedCondition,
    MilestoneCondition,
    NotCondition,
    PrestigeCountCondition,
    PronounsCondition,
    QuestStageCondition,
    SkillCondition,
)
```

**After — imports:**

```python
import datetime

from oscilla.engine import calendar_utils
from oscilla.engine.models.base import (
    AdventuresCompletedCondition,
    AllCondition,
    AnyCondition,
    AnyItemEquippedCondition,
    CharacterStatCondition,
    ChineseZodiacIsCondition,
    ClassCondition,
    Condition,
    DateIsCondition,
    DayOfWeekIsCondition,
    EnemiesDefeatedCondition,
    ItemCondition,
    ItemEquippedCondition,
    ItemHeldLabelCondition,
    LevelCondition,
    LocationsVisitedCondition,
    MilestoneCondition,
    MonthIsCondition,
    MoonPhaseIsCondition,
    NotCondition,
    PrestigeCountCondition,
    PronounsCondition,
    QuestStageCondition,
    SeasonIsCondition,
    SkillCondition,
    TimeBetweenCondition,
    ZodiacIsCondition,
)
```

**Helper added** before the `evaluate()` function:

```python
def _current_datetime(registry: "ContentRegistry | None") -> datetime.datetime:
    """Return the current datetime in the game's configured timezone."""
    tz_name: str | None = None
    if registry is not None and registry.game is not None:
        tz_name = registry.game.spec.timezone
    return calendar_utils.resolve_local_datetime(tz_name)
```

**New match cases** added to `evaluate()`, after the existing `QuestStageCondition` case and before the final `raise ValueError`:

```python
        # --- Calendar predicates ---
        # All predicates derive date/time from a single call so that all
        # conditions see a consistent moment in the game's configured timezone.
        case SeasonIsCondition(value=v):
            today = _current_datetime(registry).date()
            # Read hemisphere from game config if available; default to northern.
            hemisphere = "northern"
            if registry is not None and registry.game is not None:
                hemisphere = registry.game.spec.season_hemisphere
            elif registry is None:
                logger.debug(
                    "season_is condition evaluated without a registry — "
                    "defaulting to northern hemisphere."
                )
            return calendar_utils.season(today, hemisphere=hemisphere) == v

        case MoonPhaseIsCondition(value=v):
            return calendar_utils.moon_phase(_current_datetime(registry).date()) == v

        case ZodiacIsCondition(value=v):
            return calendar_utils.zodiac_sign(_current_datetime(registry).date()) == v

        case ChineseZodiacIsCondition(value=v):
            return calendar_utils.chinese_zodiac(_current_datetime(registry).date().year) == v

        case MonthIsCondition(value=v):
            # value is always int (normalised by model validator).
            return _current_datetime(registry).date().month == v

        case DayOfWeekIsCondition(value=v):
            # value is always int 0-6 (normalised by model validator), matching
            # Python's date.weekday() convention (Monday=0, Sunday=6).
            return _current_datetime(registry).date().weekday() == v

        case DateIsCondition(month=m, day=d, year=y):
            today = _current_datetime(registry).date()
            if y is not None and today.year != y:
                return False
            return today.month == m and today.day == d

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
```

---

### File: `oscilla/engine/templates.py`

**Change 1 — add `GameContext` dataclass** (add after `CombatContextView`):

**Before** (empty slot after `CombatContextView`):

```python
@dataclass
class ExpressionContext:
    """Complete read-only context passed to every template render call.

    combat is None for non-combat steps. Templates that reference combat.*
    will raise UndefinedError at mock-render time if the context_type is not
    'combat', which is caught as a validation error at load time.
    """

    player: PlayerContext
    combat: CombatContextView | None = None
```

**After** (insert `GameContext` before `ExpressionContext`, then update `ExpressionContext`):

```python
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
    """

    player: PlayerContext
    combat: CombatContextView | None = None
    game: GameContext = field(default_factory=GameContext)
```

Also add `field` to the `dataclasses` import:

```python
from dataclasses import dataclass, field
```

(It is already imported; verify `field` is present.)

**Change 2 — add `_MockGame` class** (add near the other mock classes):

```python
class _MockGame:
    """Mock GameContext for load-time template validation."""

    season_hemisphere: str = "northern"
    timezone: str | None = None

    def __getattr__(self, name: str) -> "Any":
        raise TemplateValidationError(f"game has no attribute {name!r}")
```

**Change 3 — update `build_mock_context`:**

**Before:**

```python
def build_mock_context(stat_names: List[str], include_combat: bool = False) -> Dict[str, Any]:
    """Build a comprehensive mock context for load-time template validation."""
    ctx: Dict[str, Any] = {"player": _MockPlayer(stat_names)}
    if include_combat:
        ctx["combat"] = _MockCombatContext()
    ctx.update(SAFE_GLOBALS)
    return ctx
```

**After:**

```python
def build_mock_context(stat_names: List[str], include_combat: bool = False) -> Dict[str, Any]:
    """Build a comprehensive mock context for load-time template validation."""
    ctx: Dict[str, Any] = {}
    ctx.update(SAFE_GLOBALS)
    ctx["player"] = _MockPlayer(stat_names)
    # Use a single _MockGame instance for both ctx["game"] and the season() closure
    # so they share the same object rather than creating two separate instances.
    mock_game = _MockGame()
    ctx["game"] = mock_game
    if include_combat:
        ctx["combat"] = _MockCombatContext()
    # Override time functions. Mock timezone is always None (server local) —
    # load-time validation needs structural correctness, not real timezone resolution.
    ctx["season"] = lambda date: calendar_utils.season(date, hemisphere=mock_game.season_hemisphere)
    ctx["today"] = lambda: datetime.date.today()
    ctx["now"] = lambda: datetime.datetime.now()
    return ctx
```

**Change 4 — update `GameTemplateEngine.render()`:**

**Before:**

```python
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
```

**After:**

```python
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
        # Override the time functions from SAFE_GLOBALS with closures that respect
        # the game's configured timezone. today() and now() return values in the
        # game's timezone; season() uses the hemisphere from that same context.
        tz = calendar_utils.resolve_local_datetime(ctx.game.timezone).tzinfo
        render_ctx["today"] = lambda: datetime.datetime.now(tz=tz).date()
        render_ctx["now"] = lambda: datetime.datetime.now(tz=tz)
        render_ctx["season"] = lambda date: calendar_utils.season(
            date, hemisphere=ctx.game.season_hemisphere
        )
        try:
            return str(template.render(**render_ctx))
        except Exception as exc:
            raise TemplateRuntimeError(f"Template {template_id!r} failed at runtime: {exc}") from exc
```

---

### File: `oscilla/engine/pipeline.py`

**Updated call site — `_build_context()`:**

**Before:**

```python
    def _build_context(self, combat_view: "CombatContextView | None" = None) -> ExpressionContext:
        """Build a read-only render context from current player state."""
        return ExpressionContext(
            player=PlayerContext.from_character(self._player),
            combat=combat_view,
        )
```

**After:**

```python
    def _build_context(self, combat_view: "CombatContextView | None" = None) -> ExpressionContext:
        """Build a read-only render context from current player state."""
        game_spec = self._registry.game.spec if self._registry.game is not None else None
        hemisphere = game_spec.season_hemisphere if game_spec is not None else "northern"
        timezone = game_spec.timezone if game_spec is not None else None
        return ExpressionContext(
            player=PlayerContext.from_character(self._player),
            combat=combat_view,
            game=GameContext(season_hemisphere=hemisphere, timezone=timezone),
        )
```

Also update the import at the top of `pipeline.py`:

**Before:**

```python
from oscilla.engine.templates import ExpressionContext, PlayerContext
```

**After:**

```python
from oscilla.engine.templates import ExpressionContext, GameContext, PlayerContext
```

---

### File: `oscilla/engine/steps/effects.py`

**Updated call site — fallback `ExpressionContext` in `run_effect()`:**

**Before:**

```python
        if ctx is None:
            ctx = ExpressionContext(player=PlayerContext.from_character(player))
```

**After:**

```python
        if ctx is None:
            from oscilla.engine.templates import GameContext
            game_spec = registry.game.spec if registry.game is not None else None
            hemisphere = game_spec.season_hemisphere if game_spec is not None else "northern"
            timezone = game_spec.timezone if game_spec is not None else None
            ctx = ExpressionContext(
                player=PlayerContext.from_character(player),
                game=GameContext(season_hemisphere=hemisphere, timezone=timezone),
            )
```

---

## Edge Cases

| Condition               | Edge Case                             | Handling                                                            |
| ----------------------- | ------------------------------------- | ------------------------------------------------------------------- |
| `season_is`             | `registry` is `None`                  | Defaults to `"northern"`, logs `debug` message                      |
| `season_is`             | `registry.game` is `None`             | Defaults to `"northern"`, no warning (valid game-less test)         |
| All calendar predicates | `timezone` is a valid IANA name       | All evaluate using that timezone's current date/time                |
| All calendar predicates | `timezone` is unrecognised IANA key   | Logs `warning`, all evaluate using server local time                |
| `time_between`          | `start == end`                        | Always returns `False`, logs `warning`                              |
| `time_between`          | `start > end`                         | Midnight-wrap interpretation (true if `now >= start OR now <= end`) |
| `date_is`               | `month=2, day=29` on a non-leap year  | Correctly false on non-leap years regardless of timezone            |
| `month_is`              | Unknown string name (e.g. `"Octobr"`) | Raises `ValueError` at parse time via Pydantic model validator      |
| `day_of_week_is`        | Unknown string name                   | Raises `ValueError` at parse time via Pydantic model validator      |

---

## Risks / Trade-offs

**Real-world time is un-seedable in tests** → Mitigation: condition evaluator calls `datetime.date.today()` and `datetime.datetime.now()`. Unit tests must monkeypatch `datetime.date.today` or call the evaluator with a fixture date adapter. Tests should cover at least one true and one false case by controlling the date.

**`timezone` configuration** → When `timezone` is not set in `game.yaml`, all calendar predicates use server local time. Game authors should set `timezone` to an IANA name (e.g. `"America/New_York"`) if their game targets a specific region's clock. Without it, a season change, zodiac change, or midnight-straddling `date_is` will occur at server-local midnight rather than the audience's midnight. Per-player timezones are a future concern not scoped here.

**`DateIsCondition` with `year` is a one-shot event** → [Non-risk]: This is the intended behavior and covered in author docs.

---

## Documentation Plan

| Document                                                   | Audience            | Topics                                                                                                                                                                                                                                                  |
| ---------------------------------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/authors/calendar-conditions.md` (new)                | Content authors     | All 8 new predicates with YAML examples; `season_hemisphere` and `timezone` game config fields; hemisphere effects on `season()`; `time_between` timezone behavior and midnight-wrapping; note that omitting `timezone` falls back to server local time |
| `docs/authors/README.md` (update)                          | Content authors     | Add `calendar-conditions.md` to table of contents                                                                                                                                                                                                       |
| `openspec/specs/condition-evaluator/spec.md` (delta)       | Engine contributors | New `Requirements` and `Scenarios` for each of the 8 new predicates                                                                                                                                                                                     |
| `openspec/specs/dynamic-content-templates/spec.md` (delta) | Engine contributors | New `GameContext` object in `ExpressionContext`; `game.season_hemisphere` property; updated `season()` description noting hemisphere-aware behavior; `season_hemisphere` field in `GameSpec`                                                            |

### `docs/authors/calendar-conditions.md` must cover

- Quick-start: one full YAML example gating an adventure on season
- All 8 predicates listed in a reference table with value domains and examples
- The `season_hemisphere` game.yaml setting with before/after examples
- `time_between` midnight-wrap behavior with explicit examples (22:00–06:00)
- `date_is` with and without year
- `month_is` and `day_of_week_is` showing both int and string forms
- `timezone` game.yaml setting: IANA name, unset = server local, with worked example
- Note that omitting `timezone` falls back to server local time (linking to deployment docs)
- Composition examples: `all` + `season_is` + `moon_phase_is`

---

## Testing Philosophy

### Unit tests: condition evaluator (`tests/engine/test_conditions.py`)

Each new predicate gets a true and a false scenario. Time-dependent calls use `monkeypatch` to freeze `datetime.date.today` and `datetime.datetime.now`. This avoids flaky tests that depend on the actual calendar.

**Required fixtures / stubs:**

```python
# conftest.py addition
import datetime
import pytest

@pytest.fixture
def freeze_date(monkeypatch):
    """Return a factory that patches _current_datetime() to a fixed moment."""
    def _freeze(year: int, month: int, day: int, hour: int = 14) -> datetime.date:
        fixed = datetime.datetime(year, month, day, hour, 0)
        # Patch calendar_utils.resolve_local_datetime so _current_datetime()
        # returns a predictable value regardless of registry timezone.
        monkeypatch.setattr(
            "oscilla.engine.calendar_utils.resolve_local_datetime",
            lambda tz_name: fixed,
        )
        return fixed.date()
    return _freeze
```

**Example test functions:**

```python
# tests/engine/test_calendar_conditions.py
import datetime
import pytest
from oscilla.engine.conditions import evaluate
from oscilla.engine.models.base import (
    SeasonIsCondition,
    MoonPhaseIsCondition,
    MonthIsCondition,
    DayOfWeekIsCondition,
    DateIsCondition,
    TimeBetweenCondition,
    ZodiacIsCondition,
    ChineseZodiacIsCondition,
)
from tests.helpers import make_player  # minimal CharacterState factory


def test_season_is_true(freeze_date) -> None:
    freeze_date(2026, 7, 15)  # July = summer (northern)
    cond = SeasonIsCondition(type="season_is", value="summer")
    assert evaluate(cond, make_player()) is True


def test_season_is_false(freeze_date) -> None:
    freeze_date(2026, 7, 15)  # July = summer, not winter
    cond = SeasonIsCondition(type="season_is", value="winter")
    assert evaluate(cond, make_player()) is False


def test_season_is_southern_hemisphere(freeze_date, mock_registry_with_hemisphere) -> None:
    freeze_date(2026, 7, 15)  # July = winter in southern hemisphere
    cond = SeasonIsCondition(type="season_is", value="winter")
    registry = mock_registry_with_hemisphere("southern")
    assert evaluate(cond, make_player(), registry=registry) is True


def test_month_is_integer(freeze_date) -> None:
    freeze_date(2026, 10, 31)
    cond = MonthIsCondition(type="month_is", value=10)
    assert evaluate(cond, make_player()) is True


def test_month_is_string(freeze_date) -> None:
    freeze_date(2026, 10, 31)
    cond = MonthIsCondition(type="month_is", value="October")
    assert evaluate(cond, make_player()) is True


def test_month_is_false(freeze_date) -> None:
    freeze_date(2026, 10, 31)
    cond = MonthIsCondition(type="month_is", value=12)
    assert evaluate(cond, make_player()) is False


def test_day_of_week_is_string(freeze_date) -> None:
    freeze_date(2026, 4, 6)  # April 6, 2026 is a Monday
    cond = DayOfWeekIsCondition(type="day_of_week_is", value="Monday")
    assert evaluate(cond, make_player()) is True


def test_date_is_annual(freeze_date) -> None:
    freeze_date(2026, 12, 25)
    cond = DateIsCondition(type="date_is", month=12, day=25)
    assert evaluate(cond, make_player()) is True


def test_date_is_wrong_year(freeze_date) -> None:
    freeze_date(2027, 12, 25)
    cond = DateIsCondition(type="date_is", month=12, day=25, year=2026)
    assert evaluate(cond, make_player()) is False


def test_time_between_normal_window(monkeypatch) -> None:
    import datetime as dt
    monkeypatch.setattr(
        "oscilla.engine.conditions.datetime",
        type("_d", (), {
            "date": dt.date,
            "datetime": type("_dt", (), {"now": staticmethod(lambda: dt.datetime(2026, 4, 5, 15, 0))}),
            "time": dt.time,
        })(),
    )
    cond = TimeBetweenCondition(type="time_between", start="10:00", end="18:00")
    assert evaluate(cond, make_player()) is True


def test_time_between_midnight_wrap_true(monkeypatch) -> None:
    import datetime as dt
    # 23:30 is after 22:00, so in the wrapping window 22:00-04:00
    monkeypatch.setattr(
        "oscilla.engine.conditions.datetime",
        type("_d", (), {
            "date": dt.date,
            "datetime": type("_dt", (), {"now": staticmethod(lambda: dt.datetime(2026, 4, 5, 23, 30))}),
            "time": dt.time,
        })(),
    )
    cond = TimeBetweenCondition(type="time_between", start="22:00", end="04:00")
    assert evaluate(cond, make_player()) is True


def test_time_between_zero_duration_false(monkeypatch) -> None:
    import datetime as dt
    monkeypatch.setattr(
        "oscilla.engine.conditions.datetime",
        type("_d", (), {
            "date": dt.date,
            "datetime": type("_dt", (), {"now": staticmethod(lambda: dt.datetime(2026, 4, 5, 12, 0))}),
            "time": dt.time,
        })(),
    )
    cond = TimeBetweenCondition(type="time_between", start="12:00", end="12:00")
    assert evaluate(cond, make_player()) is False
```

### Unit tests: `calendar_utils.py`

Add tests for the new `hemisphere` parameter to `season()`:

```python
# tests/engine/test_calendar_utils.py (additions)
import datetime
from oscilla.engine.calendar_utils import season


def test_season_southern_july() -> None:
    # July is summer in northern hemisphere, winter in southern
    d = datetime.date(2026, 7, 15)
    assert season(d, hemisphere="northern") == "summer"
    assert season(d, hemisphere="southern") == "winter"


def test_season_southern_january() -> None:
    # January is winter in northern hemisphere, summer in southern
    d = datetime.date(2026, 1, 15)
    assert season(d, hemisphere="northern") == "winter"
    assert season(d, hemisphere="southern") == "summer"
```

### Unit tests: `GameContext` in templates

```python
# tests/engine/test_templates.py (additions)
from oscilla.engine.templates import ExpressionContext, GameContext, PlayerContext
from tests.helpers import make_player_context


def test_expression_context_default_game() -> None:
    ctx = ExpressionContext(player=make_player_context())
    assert ctx.game.season_hemisphere == "northern"


def test_expression_context_custom_hemisphere() -> None:
    ctx = ExpressionContext(
        player=make_player_context(),
        game=GameContext(season_hemisphere="southern"),
    )
    assert ctx.game.season_hemisphere == "southern"
```

### Integration tests: condition composition

```python
def test_calendar_conditions_compose_with_all(freeze_date) -> None:
    # October full moon (or not-full-moon — just verify composition works)
    freeze_date(2026, 10, 31)
    from oscilla.engine.models.base import AllCondition, MonthIsCondition, MoonPhaseIsCondition
    cond = AllCondition(type="all", conditions=[
        MonthIsCondition(type="month_is", value=10),
        MoonPhaseIsCondition(type="moon_phase_is", value=calendar_utils.moon_phase(datetime.date(2026, 10, 31))),
    ])
    assert evaluate(cond, make_player()) is True
```

### Test tiers summary

| Tier                    | Files                                      | What is verified                                                                                                          |
| ----------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| Unit — `calendar_utils` | `tests/engine/test_calendar_utils.py`      | `season()` hemisphere parameter (northern and southern for each of 12 months)                                             |
| Unit — condition models | `tests/engine/test_calendar_conditions.py` | Parse-time normalisation; true/false for each of 8 predicates; midnight-wrap; zero-duration; southern hemisphere registry |
| Unit — templates        | `tests/engine/test_templates.py`           | `GameContext` default; custom hemisphere; `season()` override in render context                                           |
| Integration             | `tests/engine/test_calendar_conditions.py` | `all`/`any`/`not` composition with calendar predicates                                                                    |

---

## Testlandia Integration

A new **Calendar Conditions** location is added to the existing `conditions` region in `content/testlandia/regions/conditions/`. It exposes a set of adventures, each testing one predicate family, so a developer can manually verify each condition type by playing through.

### New files

```
content/testlandia/regions/conditions/locations/calendar/
    calendar.yaml                     ← Location manifest
    adventures/
        test-season-is.yaml           ← season_is (current season detected, shown in text)
        test-moon-phase-is.yaml       ← moon_phase_is (always accessible, shows current phase)
        test-month-is.yaml            ← month_is using string name
        test-day-of-week-is.yaml      ← day_of_week_is using string name
        test-date-is.yaml             ← date_is without year (Dec 25 only)
        test-time-between.yaml        ← time_between (business hours 09:00–17:00)
        test-zodiac-is.yaml           ← zodiac_is (current sign shown)
        test-moon-phase-show.yaml     ← unconditioned adventure that prints current moon phase
```

**`calendar.yaml`** (location manifest):

```yaml
apiVersion: oscilla/v1
kind: Location
metadata:
  name: test-calendar
spec:
  displayName: "Calendar Conditions Lab"
  description: "Adventures gated on real-world time. Use these to verify calendar condition predicates manually."
  region: conditions
  adventures:
    - ref: test-season-is
      weight: 100
    - ref: test-moon-phase-is
      weight: 100
    - ref: test-month-is
      weight: 100
    - ref: test-day-of-week-is
      weight: 100
    - ref: test-date-is
      weight: 100
    - ref: test-time-between
      weight: 100
    - ref: test-zodiac-is
      weight: 100
    - ref: test-moon-phase-show
      weight: 100
```

**`test-season-is.yaml`** (demonstrates `season_is`):

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-season-is
spec:
  displayName: "Season Gate Test"
  description: "Locked to the current season."
  unlock:
    type: season_is
    value: "{{ season(today()) }}" # This is a template — for illustration only;
    # In practice, the unlock uses a static value like "summer".
    # The adventure below uses no gating — instead it demonstrates by running
    # four sub-adventures (one per season, each locked to that season).
  steps:
    - type: narrative
      text: "You are in the {{ season(today()) }} season. This text always renders."
```

Because `season_is` is a static predicate (not template-driven), the testlandia content for conditions must include **one adventure per season value** with its unlock set to the relevant season. Given that only one will be in pool at any given time, a developer can switch their system clock or review the code to verify each branch.

More practically, the adventures should use the `all` composition to test multiple conditions at once.

**`test-moon-phase-show.yaml`** (no gating — always available, shows current values):

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: test-moon-phase-show
spec:
  displayName: "Calendar Info"
  description: "Always accessible. Shows current calendar state for verification."
  steps:
    - type: narrative
      text: |
        Calendar debug info:
        - Date: {{ today() }}
        - Season: {{ season(today()) }}
        - Moon phase: {{ moon_phase(today()) }}
        - Zodiac: {{ zodiac_sign(today()) }}
        - Chinese zodiac: {{ chinese_zodiac(today().year) }}
        - Day of week: {{ day_name(today().weekday()) }}
        - Month: {{ month_name(today().month) }}
```

This "always-on" adventure lets a developer immediately verify that template functions return the expected values before manually testing gated adventures.

**Developer QA instructions** (added to testlandia docs):

1. Run `test-moon-phase-show` to see current calendar state
2. Verify the `test-season-is` adventures — only the current season's adventure should appear in pool
3. Set system time to 22:30 and run `test-time-between` — should not appear if after 17:00
4. On December 25 (or modify `DateIsCondition` in a test game), run `test-date-is`

---

## Migration Plan

No database migrations required. No player state changes. No breaking changes to existing content.

Authors using `season()` in templates will see no behavior change — the default hemisphere is `"northern"`, matching the previous hardcoded behavior.

Content packages that do not declare `season_hemisphere` in `game.yaml` receive the default and are unaffected.

---

## Open Questions

All design decisions are resolved. No open questions.

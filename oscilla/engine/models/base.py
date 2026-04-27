"""Base manifest envelope and shared condition models.

All manifest kinds share the same apiVersion/kind/metadata/spec envelope.
Condition models are defined here and imported by other manifest modules.
"""

from __future__ import annotations

import calendar as _calendar_module  # stdlib; aliased to avoid shadowing local variables
from typing import Annotated, Dict, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Metadata(BaseModel):
    name: str = Field(description="Unique identifier for this entity within its kind.")
    abstract: bool = Field(
        default=False,
        description="If true, this manifest is a template-only base and will not be registered at runtime.",
    )
    base: str | None = Field(
        default=None,
        description="Name of another same-kind manifest to inherit unspecified spec fields from.",
    )


class BaseSpec(BaseModel):
    """Parent class for all spec models. Provides the properties dict for manifest-level constants."""

    properties: Dict[str, int | float | str | bool] = Field(
        default_factory=dict,
        description="Static manifest-level values available as 'this' in formula and template contexts.",
    )


class ManifestEnvelope(BaseModel):
    apiVersion: Literal["oscilla/v1"]
    kind: str
    metadata: Metadata
    spec: object  # overridden by each kind with a strongly-typed spec model


# ---------------------------------------------------------------------------
# Shared helper for numeric comparisons used by several condition leaf types.
# ---------------------------------------------------------------------------


class ModComparison(BaseModel):
    divisor: int = Field(ge=1, description="Divisor for the modulo check.")
    remainder: int = Field(default=0, ge=0, description="Expected remainder.")

    @model_validator(mode="after")
    def validate_remainder_in_range(self) -> "ModComparison":
        if self.remainder >= self.divisor:
            raise ValueError(
                f"mod.remainder must be in [0, divisor-1]; got remainder={self.remainder}, divisor={self.divisor}"
            )
        return self


# ---------------------------------------------------------------------------
# Condition leaf nodes
# ---------------------------------------------------------------------------


class LevelCondition(BaseModel):
    type: Literal["level"]
    value: int = Field(ge=1)


class GrantRecord(BaseModel):
    """Records the tick and real-world timestamp at which a milestone or archetype was granted."""

    tick: int = Field(description="Value of internal_ticks at the moment this record was created.")
    timestamp: int = Field(description="Unix timestamp (seconds) at the moment this record was created.")


class MilestoneCondition(BaseModel):
    type: Literal["milestone"]
    name: str


class MilestoneTicksElapsedCondition(BaseModel):
    """True when the ticks elapsed since a milestone was granted satisfies the comparator.

    elapsed = player.internal_ticks - milestone.tick (the grant tick).
    Returns False if the milestone has not been granted.
    At least one of gte / lte must be set.
    """

    type: Literal["milestone_ticks_elapsed"]
    name: str = Field(description="Milestone name to look up.")
    gte: int | None = None
    lte: int | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "MilestoneTicksElapsedCondition":
        if self.gte is None and self.lte is None:
            raise ValueError("milestone_ticks_elapsed condition must specify at least one of: gte, lte")
        return self


class HasArchetypeCondition(BaseModel):
    """True when the character currently holds the named archetype."""

    type: Literal["has_archetype"]
    name: str


class HasAllArchetypesCondition(BaseModel):
    """True when the character holds every archetype in the list."""

    type: Literal["has_all_archetypes"]
    names: List[str]


class HasAnyArchetypeCondition(BaseModel):
    """True when the character holds at least one archetype in the list."""

    type: Literal["has_any_archetypes"]
    names: List[str]


class ArchetypeCountCondition(BaseModel):
    """True when the number of held archetypes satisfies the comparator.

    Same comparison pattern as PrestigeCountCondition.
    At least one of gt / gte / lt / lte / eq / mod must be set.
    """

    type: Literal["archetype_count"]
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None
    mod: ModComparison | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "ArchetypeCountCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq, self.mod]):
            raise ValueError("archetype_count condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self


class ArchetypeTicksElapsedCondition(BaseModel):
    """True when the ticks elapsed since an archetype was granted satisfies the comparator.

    elapsed = player.internal_ticks - archetype.tick (the grant tick).
    Returns False if the archetype is not currently held.
    At least one of gte / lte must be set.
    """

    type: Literal["archetype_ticks_elapsed"]
    name: str = Field(description="Archetype name to look up.")
    gte: int | None = None
    lte: int | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "ArchetypeTicksElapsedCondition":
        if self.gte is None and self.lte is None:
            raise ValueError("archetype_ticks_elapsed condition must specify at least one of: gte, lte")
        return self


class ItemCondition(BaseModel):
    type: Literal["item"]
    name: str  # item manifest name; true if quantity > 0


class ItemEquippedCondition(BaseModel):
    type: Literal["item_equipped"]
    name: str  # non-stackable item manifest name; true when equipped


class ItemHeldLabelCondition(BaseModel):
    type: Literal["item_held_label"]
    label: str  # true when any held item (stack or instance) has this label


class AnyItemEquippedCondition(BaseModel):
    type: Literal["any_item_equipped"]
    label: str  # true when any equipped instance has this label


class CharacterStatCondition(BaseModel):
    type: Literal["character_stat"]
    name: str
    gt: int | float | None = None
    gte: int | float | None = None
    lt: int | float | None = None
    lte: int | float | None = None
    eq: int | float | None = None
    mod: ModComparison | None = None
    # Whether to evaluate against base stats or effective stats (with gear bonuses).
    # Defaults to "effective" for equip-requirement use cases.
    stat_source: Literal["base", "effective"] = "effective"

    @model_validator(mode="after")
    def require_comparator(self) -> "CharacterStatCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq, self.mod]):
            raise ValueError("character_stat condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self


class PrestigeCountCondition(BaseModel):
    type: Literal["prestige_count"]
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None
    mod: ModComparison | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "PrestigeCountCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq, self.mod]):
            raise ValueError("prestige_count condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self


class EnemiesDefeatedCondition(BaseModel):
    type: Literal["enemies_defeated"]
    name: str
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None
    mod: ModComparison | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "EnemiesDefeatedCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq, self.mod]):
            raise ValueError("enemies_defeated condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self


class LocationsVisitedCondition(BaseModel):
    type: Literal["locations_visited"]
    name: str
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None
    mod: ModComparison | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "LocationsVisitedCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq, self.mod]):
            raise ValueError("locations_visited condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self


class AdventuresCompletedCondition(BaseModel):
    type: Literal["adventures_completed"]
    name: str
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None
    mod: ModComparison | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "AdventuresCompletedCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq, self.mod]):
            raise ValueError("adventures_completed condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self


class PronounsCondition(BaseModel):
    type: Literal["pronouns"]
    set: str = Field(description="Pronoun set key to match (e.g. 'they_them', 'she_her', 'he_him').")


class SkillCondition(BaseModel):
    type: Literal["skill"]
    name: str = Field(description="Skill manifest name to check.")
    mode: Literal["available", "learned"] = Field(
        default="available",
        description=(
            "'available' — checks known_skills ∪ item-granted skills (requires registry). "
            "'learned' — checks known_skills only (registry not required)."
        ),
    )


class QuestStageCondition(BaseModel):
    type: Literal["quest_stage"]
    quest: str = Field(description="Quest manifest name.")
    stage: str = Field(description="Quest stage name that must be the current active stage.")


class NameEqualsCondition(BaseModel):
    type: Literal["name_equals"]
    value: str = Field(description="The exact character name to compare against.")


# ---------------------------------------------------------------------------
# Normalisation helpers for calendar condition models
# ---------------------------------------------------------------------------


def _resolve_month(value: int | str) -> int:
    """Normalize a month value to an integer 1-12.

    Accepts int (1-12) or full English month name (case-insensitive).
    Raises ValueError for unrecognized values.
    """
    if isinstance(value, int):
        if not (1 <= value <= 12):
            raise ValueError(f"month must be 1-12, got {value}")
        return value
    # calendar.month_name is 1-indexed; index 0 is the empty string.
    for i in range(1, 13):
        if _calendar_module.month_name[i].lower() == value.lower():
            return i
    raise ValueError(f"Unrecognized month name: {value!r}")


def _resolve_weekday(value: int | str) -> int:
    """Normalize a day-of-week value to an integer 0-6 (Monday=0, Sunday=6).

    Accepts int (0-6) or full English weekday name (case-insensitive).
    Raises ValueError for unrecognized values.
    """
    if isinstance(value, int):
        if not (0 <= value <= 6):
            raise ValueError(f"day_of_week must be 0-6, got {value}")
        return value
    for i in range(7):
        if _calendar_module.day_name[i].lower() == value.lower():
            return i
    raise ValueError(f"Unrecognized weekday name: {value!r}")


# ---------------------------------------------------------------------------
# Calendar condition leaf nodes
# ---------------------------------------------------------------------------


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
        "Aries",
        "Taurus",
        "Gemini",
        "Cancer",
        "Leo",
        "Virgo",
        "Libra",
        "Scorpio",
        "Sagittarius",
        "Capricorn",
        "Aquarius",
        "Pisces",
    ]


class ChineseZodiacIsCondition(BaseModel):
    type: Literal["chinese_zodiac_is"]
    value: Literal[
        "Rat",
        "Ox",
        "Tiger",
        "Rabbit",
        "Dragon",
        "Snake",
        "Horse",
        "Goat",
        "Monkey",
        "Rooster",
        "Dog",
        "Pig",
    ]


class MonthIsCondition(BaseModel):
    """True when today's month matches the given value.

    Accepts an integer (1-12) or a full English month name ("January"..."December").
    Normalized to int by model validator.
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
    Normalized to int by model validator.
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


class DateBoundary(BaseModel):
    """A month/day pair used as a start or end point in DateBetweenCondition."""

    model_config = ConfigDict(frozen=True)
    month: int | str
    day: int = Field(ge=1, le=31)

    @model_validator(mode="after")
    def normalise_month(self) -> "DateBoundary":
        object.__setattr__(self, "month", _resolve_month(self.month))
        return self


class DateBetweenCondition(BaseModel):
    """True when today falls within the date range [start, end] (month/day only).

    When start comes after end in the calendar year, the range wraps across
    the year boundary (e.g. start=Dec 1, end=Jan 31 covers December and January).
    When start == end the condition always evaluates False and logs a warning.
    No year field is provided; use DateIsCondition or combine with AllCondition
    for year-specific date ranges.
    """

    type: Literal["date_between"]
    start: DateBoundary
    end: DateBoundary


class TimeBetweenCondition(BaseModel):
    """True when the current local time falls in the window [start, end].

    Both values are HH:MM strings in 24-hour format.
    When start > end the window wraps midnight (e.g. 22:00–04:00 is "night").
    When start == end the window has zero duration and always evaluates False.
    """

    type: Literal["time_between"]
    start: str = Field(pattern=r"^\d{2}:\d{2}$", description="HH:MM (24-hour)")
    end: str = Field(pattern=r"^\d{2}:\d{2}$", description="HH:MM (24-hour)")


# ---------------------------------------------------------------------------
# Condition branch nodes (forward-referenced via model_rebuild)
# ---------------------------------------------------------------------------


class AllCondition(BaseModel):
    type: Literal["all"]
    conditions: List["Condition"] = Field(min_length=1)


class AnyCondition(BaseModel):
    type: Literal["any"]
    conditions: List["Condition"] = Field(min_length=1)


class NotCondition(BaseModel):
    type: Literal["not"]
    condition: "Condition"


class GameCalendarTimeCondition(BaseModel):
    """Numeric comparison against internal_ticks or game_ticks.

    clock: "internal" (default) uses internal_ticks — the monotone clock.
           "game" uses game_ticks — the narrative clock, adjustable by effects.

    At least one of gt/gte/lt/lte/eq/mod must be set.
    Only valid when game.time is configured; evaluates False with a warning otherwise.
    """

    type: Literal["game_calendar_time_is"]
    clock: Literal["internal", "game"] = "internal"
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None
    mod: "ModComparison | None" = None

    @model_validator(mode="after")
    def at_least_one_comparator(self) -> "GameCalendarTimeCondition":
        if all(v is None for v in (self.gt, self.gte, self.lt, self.lte, self.eq, self.mod)):
            raise ValueError("game_calendar_time_is condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self


class GameCalendarCycleCondition(BaseModel):
    """Tests the current label of any named cycle against a value.

    cycle: the cycle name or alias to query.
    value: the expected label string. Validated against declared labels at load time
           by the semantic validator.

    Only valid when game.time defines the named cycle; evaluates False with a warning otherwise.
    """

    type: Literal["game_calendar_cycle_is"]
    cycle: str
    value: str


class GameCalendarEraCondition(BaseModel):
    """Tests whether a named era is currently active or inactive.

    era: the era name to query.
    state: "active" (default) evaluates to True when the era's condition is met.
           "inactive" is the logical negation.

    Only valid when game.time defines the named era; evaluates False with a warning otherwise.
    """

    type: Literal["game_calendar_era_is"]
    era: str
    state: Literal["active", "inactive"] = "active"


class CustomConditionRef(BaseModel):
    """Reference to a named CustomCondition manifest declared in the same content package.

    Resolved at evaluation time against registry.custom_conditions.
    Validated at load time: dangling references and circular dependency chains
    both raise ContentLoadError.
    """

    type: Literal["custom"]
    name: str


class EnemyStatCondition(BaseModel):
    """True when an enemy stat satisfies the comparator. Only valid during combat.

    Returns False with a logger.warning when evaluated outside a combat context
    (i.e., when enemy_stats is not passed to evaluate()).
    At least one of gt/gte/lt/lte/eq must be set.
    """

    type: Literal["enemy_stat"]
    stat: str = Field(description="Enemy stat key to compare against.")
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "EnemyStatCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq]):
            raise ValueError("enemy_stat condition must specify at least one of: gt, gte, lt, lte, eq")
        return self


class CombatStatCondition(BaseModel):
    """True when a combat-scoped stat satisfies the comparator. Only valid during combat.

    Returns False with a logger.warning when evaluated outside a combat context
    (i.e., when combat_stats is not passed to evaluate()).
    At least one of gt/gte/lt/lte/eq must be set.
    """

    type: Literal["combat_stat"]
    stat: str = Field(description="Combat stat key to compare against.")
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "CombatStatCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq]):
            raise ValueError("combat_stat condition must specify at least one of: gt, gte, lt, lte, eq")
        return self


Condition = Annotated[
    Union[
        AllCondition,
        AnyCondition,
        NotCondition,
        GameCalendarTimeCondition,
        GameCalendarCycleCondition,
        GameCalendarEraCondition,
        LevelCondition,
        MilestoneCondition,
        MilestoneTicksElapsedCondition,
        HasArchetypeCondition,
        HasAllArchetypesCondition,
        HasAnyArchetypeCondition,
        ArchetypeCountCondition,
        ArchetypeTicksElapsedCondition,
        ItemCondition,
        ItemEquippedCondition,
        ItemHeldLabelCondition,
        AnyItemEquippedCondition,
        CharacterStatCondition,
        PrestigeCountCondition,
        EnemiesDefeatedCondition,
        LocationsVisitedCondition,
        AdventuresCompletedCondition,
        SkillCondition,
        PronounsCondition,
        QuestStageCondition,
        NameEqualsCondition,
        # Calendar predicates
        SeasonIsCondition,
        MoonPhaseIsCondition,
        ZodiacIsCondition,
        ChineseZodiacIsCondition,
        MonthIsCondition,
        DayOfWeekIsCondition,
        DateIsCondition,
        DateBetweenCondition,
        TimeBetweenCondition,
        CustomConditionRef,
        EnemyStatCondition,
        CombatStatCondition,
    ],
    Field(discriminator="type"),
]

AllCondition.model_rebuild()
AnyCondition.model_rebuild()
NotCondition.model_rebuild()

"""Game manifest — global settings for a content package."""

from typing import Dict, List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import Condition, ManifestEnvelope
from oscilla.engine.models.item import StatModifier
from oscilla.engine.models.time import GameTimeSpec


class HpFormula(BaseModel):
    base_hp: int = Field(ge=1)
    hp_per_level: int = Field(ge=0)


class ItemLabelDef(BaseModel):
    """Author-defined display vocabulary entry for item labels.

    Used to declare valid label names, assign display colors, and set
    sort priority for the inventory screen.
    """

    name: str
    color: str = ""
    description: str = ""
    sort_priority: int = 0


class PassiveEffect(BaseModel):
    """A condition-gated set of stat modifiers and skill grants applied continuously.

    Evaluated in `effective_stats()` and `available_skills()` whenever the
    condition is satisfied. Registry is not available during evaluation, so
    conditions that require item lookups (item_held_label, any_item_equipped)
    are flagged as warnings by the loader.
    """

    condition: Condition | None = None
    # Stat deltas applied when the condition is satisfied.
    stat_modifiers: List[StatModifier] = []
    # Skill refs granted when the condition is satisfied.
    skill_grants: List[str] = []


class StatThresholdTrigger(BaseModel):
    """A stat threshold that fires a named trigger when crossed upward."""

    # The stat name to watch (must match a stat in character_config.yaml).
    stat: str
    # Fires when stat value transitions from < threshold to >= threshold.
    threshold: int
    # The trigger name this entry maps to in trigger_adventures.
    name: str


class GameRejoinTrigger(BaseModel):
    """Configuration for the on_game_rejoin built-in trigger."""

    # Minimum absence in hours before the rejoin trigger fires.
    absence_hours: int = Field(ge=1)


class GameTriggers(BaseModel):
    """All trigger configuration for the game package."""

    # Names of custom triggers that can be emitted via emit_trigger effect.
    # Must be declared here before they can be used — typos caught at load time.
    custom: List[str] = []
    # Configuration for the on_game_rejoin trigger.
    # Absent = on_game_rejoin trigger is never fired even if wired in trigger_adventures.
    on_game_rejoin: GameRejoinTrigger | None = None
    # Named stat threshold triggers. Each entry must have a unique `name`.
    on_stat_threshold: List[StatThresholdTrigger] = []
    # Maximum number of pending_triggers entries allowed before new appends are
    # dropped with a warning. Raise this only if your content requires deep chains.
    max_trigger_queue_depth: int = Field(default=6, ge=1)


class GameSpec(BaseModel):
    displayName: str
    description: str = ""
    # XP required to reach each level. Index 0 = XP to reach level 2, etc.
    xp_thresholds: List[int] = Field(min_length=1)
    hp_formula: HpFormula
    # Author-defined label vocabulary for items.
    item_labels: List[ItemLabelDef] = []
    # Condition-gated stat modifiers and skill grants evaluated continuously.
    passive_effects: List[PassiveEffect] = []
    # Custom outcome names beyond the three engine-internal defaults (completed, defeated, fled).
    outcomes: List[str] = Field(default_factory=list)
    # Hemisphere used by season() to compute meteorological seasons.
    # "northern" (default) or "southern". Only affects season(); all other
    # calendar functions are hemisphere-agnostic.
    season_hemisphere: Literal["northern", "southern"] = "northern"
    # IANA timezone name (e.g. "America/New_York") used by calendar predicates.
    # Defaults to None (server local time).
    timezone: str | None = None
    # Optional in-game time system. When absent, all ingame_time features
    # are disabled and existing behaviour is fully preserved.
    time: GameTimeSpec | None = None
    # Trigger configuration. Absent = no triggers defined.
    triggers: GameTriggers = Field(default_factory=GameTriggers)
    # Maps trigger name → ordered list of adventure refs to run.
    # Valid keys: on_character_create, on_level_up, on_outcome_<name>,
    #             on_game_rejoin, <threshold.name>, <custom trigger name>.
    # Validated at load time against the known trigger vocabulary.
    trigger_adventures: Dict[str, List[str]] = Field(default_factory=dict)


class GameManifest(ManifestEnvelope):
    kind: Literal["Game"]
    spec: GameSpec

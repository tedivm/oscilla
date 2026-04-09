"""Game manifest — global settings for a content package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import Condition, ManifestEnvelope
from oscilla.engine.models.item import StatModifier
from oscilla.engine.models.time import GameTimeSpec

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import Effect


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


StatThresholdFireMode = Literal["each", "highest"]


class StatThresholdTrigger(BaseModel):
    """A stat threshold that fires a named trigger when crossed upward."""

    # The stat name to watch (must match a stat in character_config.yaml).
    stat: str
    # Fires when stat value transitions from < threshold to >= threshold.
    threshold: int
    # The trigger name this entry maps to in trigger_adventures.
    name: str
    # Controls how multi-cross firing behaves when multiple thresholds are
    # crossed in a single stat mutation:
    #   "each"    — fire once per threshold crossed (ascending order)
    #   "highest" — fire only the single highest threshold crossed
    # Default: "each" (backward-compatible with existing threshold entries).
    fire_mode: StatThresholdFireMode = "each"


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


class CharacterCreationDefaults(BaseModel):
    """Author-declared defaults for newly created characters.

    Use this in biographic or linear-narrative games where the protagonist has a fixed
    identity — no player selection steps are needed.

    - ``default_name``: Used instead of the UUID placeholder in _create_new_character().
      Because it is not a UUID placeholder, SetNameEffect detects it as a real name and
      skips the prompt. Authors simply omit the type: set_name step from their creation
      adventure.
    - ``default_pronouns``: Initial pronoun-set key (e.g. 'she_her'). Overrides the
      system default (they/them). Validated at load time against known pronoun sets.
    """

    default_name: str | None = Field(
        default=None,
        description="Fixed protagonist name. Bypasses the SetNameEffect prompt.",
    )
    default_pronouns: str | None = Field(
        default=None,
        description="Initial pronoun-set key (e.g. 'she_her'). Overrides the system default (they/them).",
    )


class PrestigeConfig(BaseModel):
    """Author-defined prestige reset behavior for the game package.

    Declared once in game.yaml under the ``prestige:`` key.
    Absent = prestige is not available; any adventure using type: prestige
    will raise a ContentLoadError at content load time.
    """

    # Stats (by name) whose current value is copied from the old iteration to the new
    # iteration AFTER config defaults are applied.
    carry_stats: List[str] = Field(default_factory=list)
    # Skill refs whose membership in known_skills carries to the new iteration.
    carry_skills: List[str] = Field(default_factory=list)
    # Milestone refs that are re-granted on the new iteration if they were set on the
    # old iteration at the time of prestige.
    carry_milestones: List[str] = Field(default_factory=list)
    # Effects that run against the OLD character state just before the reset.
    # Use this to grant legacy bonuses (stat_change, milestone_grant, etc.).
    pre_prestige_effects: List["Effect"] = Field(default_factory=list)
    # Effects that run against the NEW (reset) character state immediately after the
    # reset and carry-forward are applied.
    post_prestige_effects: List["Effect"] = Field(default_factory=list)


class GameSpec(BaseModel):
    displayName: str
    description: str = ""
    # xp_thresholds and hp_formula removed — XP thresholds are now declared as
    # on_stat_threshold entries in triggers; HP initialization is done via
    # on_character_create trigger adventures.
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
    # Valid keys: on_character_create, on_outcome_<name>,
    #             on_game_rejoin, <threshold.name>, <custom trigger name>.
    # Validated at load time against the known trigger vocabulary.
    trigger_adventures: Dict[str, List[str]] = Field(default_factory=dict)
    # Optional character creation defaults. Absent = UUID placeholder name + they/them pronouns.
    character_creation: CharacterCreationDefaults | None = None
    # Optional prestige configuration. Absent = prestige is disabled.
    # Any adventure using type: prestige raises a ContentLoadError if this is None.
    prestige: PrestigeConfig | None = None


class GameManifest(ManifestEnvelope):
    kind: Literal["Game"]
    spec: GameSpec


# PrestigeConfig.pre_prestige_effects / post_prestige_effects reference Effect, which is defined
# in adventure.py. Import at rebuild time to avoid a circular import at module load.
from oscilla.engine.models.adventure import Effect as _Effect  # noqa: E402

PrestigeConfig.model_rebuild(_types_namespace={"Effect": _Effect})

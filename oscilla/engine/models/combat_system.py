"""CombatSystem manifest model — pluggable combat resolution for the engine."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal

from pydantic import BaseModel, Field, model_validator

from oscilla.engine.models.base import Condition, ManifestEnvelope

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import Effect


class CombatStatEntry(BaseModel):
    """Declares an ephemeral stat scoped to a single combat instance."""

    name: str = Field(description="Stat name. Accessible as combat_stats['name'] in formulas.")
    default: int = Field(default=0, description="Initial value when a new combat begins.")


class SystemSkillEntry(BaseModel):
    """A built-in skill available in the choice-mode action menu for this combat system.

    The skill is shown every round unless `condition` evaluates to False, in which
    case the option is silently hidden that round.
    """

    skill: str = Field(description="Skill manifest name.")
    condition: Condition | None = None


class ThresholdEffectBand(BaseModel):
    """A range-based outcome band fired after a DamageFormulaEntry result is applied.

    At least one of `min` or `max` must be set. Both are inclusive bounds.
    The first matching band fires; remaining bands are skipped.
    """

    min: int | None = Field(default=None, description="Inclusive lower bound. Omit for no lower limit.")
    max: int | None = Field(default=None, description="Inclusive upper bound. Omit for no upper limit.")
    effects: List["Effect"] = Field(description="Effects to fire when the formula result falls within [min, max].")

    @model_validator(mode="after")
    def require_at_least_one_bound(self) -> "ThresholdEffectBand":
        if self.min is None and self.max is None:
            raise ValueError("ThresholdEffectBand must specify at least one of: min, max")
        return self


class DamageFormulaEntry(BaseModel):
    """A single formula entry that applies a result to a stat namespace.

    When `target_stat` is None, the formula result is not applied to any stat;
    only `threshold_effects` fire. A formula with `target_stat: null` and an
    empty `threshold_effects` list is a hard model error (it would do nothing).
    """

    target_stat: str | None = Field(
        default=None,
        description=(
            "Stat name to mutate in the target namespace. "
            "When null, only threshold_effects fire (the result is not applied as damage)."
        ),
    )
    target: Literal["player", "enemy", "combat"] | None = Field(
        default=None,
        description=(
            "Stat namespace to target. When None, defaults to 'enemy' for player/skill formulas "
            "and 'player' for enemy formulas."
        ),
    )
    formula: str = Field(description="Jinja2 template string that renders to an integer result.")
    display: str | None = Field(
        default=None,
        description="Optional HUD display label. Stats with a label appear in the combat HUD.",
    )
    threshold_effects: List[ThresholdEffectBand] = Field(
        default_factory=list,
        description="Outcome bands fired based on the formula result.",
    )

    @model_validator(mode="after")
    def require_threshold_effects_when_no_target_stat(self) -> "DamageFormulaEntry":
        if self.target_stat is None and not self.threshold_effects:
            raise ValueError(
                "DamageFormulaEntry: target_stat is null but threshold_effects is empty — "
                "this formula would do nothing. Either set target_stat or add threshold_effects."
            )
        return self


class CombatSystemSpec(BaseModel):
    """Full specification for a combat encounter resolution system.

    The engine reads this manifest to determine turn order, defeat conditions,
    damage formulas, and lifecycle hooks. No combat arithmetic lives in the engine.
    """

    # --- Required defeat conditions ---
    player_defeat_condition: Condition = Field(
        description="Condition evaluated each round to check if the player has been defeated."
    )
    enemy_defeat_condition: Condition = Field(
        description="Condition evaluated each round to check if the enemy has been defeated."
    )

    # --- Damage formulas ---
    player_damage_formulas: List[DamageFormulaEntry] = Field(
        default_factory=list,
        description=(
            "Ordered list of formulas applied during the player's turn in 'auto' mode. "
            "Ignored when player_turn_mode is 'choice'."
        ),
    )
    enemy_damage_formulas: List[DamageFormulaEntry] = Field(
        default_factory=list,
        description="Ordered list of formulas applied during the enemy's turn each round.",
    )
    resolution_formulas: List[DamageFormulaEntry] = Field(
        default_factory=list,
        description=(
            "Ordered list of formulas applied once per round after all actor phases, "
            "before defeat conditions are evaluated. Fires in all turn_order modes."
        ),
    )

    # --- Turn structure ---
    player_turn_mode: Literal["auto", "choice"] = Field(
        default="auto",
        description=(
            "'auto' fires player_damage_formulas automatically. "
            "'choice' presents the player with a skill/item action menu each round."
        ),
    )
    turn_order: Literal["player_first", "enemy_first", "initiative", "simultaneous"] = Field(
        default="player_first",
        description=(
            "Controls which side acts first. "
            "'player_first' (default) preserves pre-refactor behavior. "
            "'initiative' uses formula rolls to determine order each round. "
            "'simultaneous' runs both phases before any defeat check."
        ),
    )
    player_initiative_formula: str | None = Field(
        default=None,
        description="Required when turn_order is 'initiative'. Higher result acts first.",
    )
    enemy_initiative_formula: str | None = Field(
        default=None,
        description="Required when turn_order is 'initiative'. Higher result acts first.",
    )
    initiative_tie: Literal["player_first", "enemy_first"] = Field(
        default="player_first",
        description="Tie-breaking rule for equal initiative rolls.",
    )
    simultaneous_defeat_result: Literal["player_wins", "enemy_wins", "both_lose"] = Field(
        default="player_wins",
        description=(
            "Outcome when both defeat conditions are satisfied simultaneously. "
            "Only meaningful when turn_order is 'simultaneous'."
        ),
    )

    # --- Skill and item scoping ---
    skill_contexts: List[str] = Field(
        default_factory=list,
        description=(
            "Context strings that make skills and items eligible for this combat system. "
            "A skill or item is available when its contexts list intersects this list."
        ),
    )
    system_skills: List[SystemSkillEntry] = Field(
        default_factory=list,
        description=(
            "Built-in skills always present in the choice-mode action menu regardless of the player's learned skills."
        ),
    )

    # --- Lifecycle hooks ---
    on_combat_start: List["Effect"] = Field(
        default_factory=list,
        description="Effects fired once when a new combat begins (not on resume from saved state).",
    )
    on_combat_end: List["Effect"] = Field(
        default_factory=list,
        description="Effects fired once when combat resolves, regardless of outcome.",
    )
    on_combat_victory: List["Effect"] = Field(
        default_factory=list,
        description="Effects fired after on_combat_end on a player win.",
    )
    on_combat_defeat: List["Effect"] = Field(
        default_factory=list,
        description="Effects fired after on_combat_end on a player loss.",
    )
    on_round_end: List["Effect"] = Field(
        default_factory=list,
        description=(
            "Effects fired at the end of each complete round, after defeat checks, "
            "only when no defeat occurred that round."
        ),
    )

    # --- Ephemeral combat stats ---
    combat_stats: List[CombatStatEntry] = Field(
        default_factory=list,
        description=(
            "Ephemeral integer stats scoped to the combat instance. "
            "Initialized from defaults when a new combat begins; discarded when combat ends."
        ),
    )


class CombatSystemManifest(ManifestEnvelope):
    kind: Literal["CombatSystem"]
    spec: CombatSystemSpec


class CombatStepOverrides(BaseModel):
    """Per-step overrides for a CombatSystemSpec.

    Any field set to a non-None value replaces the corresponding field in the
    resolved CombatSystem for this encounter only. Absent fields (None) leave
    the base CombatSystem values intact.
    """

    player_defeat_condition: Condition | None = None
    enemy_defeat_condition: Condition | None = None
    player_damage_formulas: List[DamageFormulaEntry] | None = None
    enemy_damage_formulas: List[DamageFormulaEntry] | None = None
    resolution_formulas: List[DamageFormulaEntry] | None = None
    player_turn_mode: Literal["auto", "choice"] | None = None
    turn_order: Literal["player_first", "enemy_first", "initiative", "simultaneous"] | None = None
    player_initiative_formula: str | None = None
    enemy_initiative_formula: str | None = None
    initiative_tie: Literal["player_first", "enemy_first"] | None = None
    simultaneous_defeat_result: Literal["player_wins", "enemy_wins", "both_lose"] | None = None
    skill_contexts: List[str] | None = None
    system_skills: List[SystemSkillEntry] | None = None
    on_combat_start: List["Effect"] | None = None
    on_combat_end: List["Effect"] | None = None
    on_combat_victory: List["Effect"] | None = None
    on_combat_defeat: List["Effect"] | None = None
    on_round_end: List["Effect"] | None = None
    combat_stats: List[CombatStatEntry] | None = None


# ---------------------------------------------------------------------------
# Resolve forward references: Effect is defined in adventure.py, which imports
# CombatStepOverrides from this module — import late to break the cycle.
# ---------------------------------------------------------------------------
from oscilla.engine.models.adventure import Effect as _Effect  # noqa: E402

ThresholdEffectBand.model_rebuild(_types_namespace={"Effect": _Effect})
CombatSystemSpec.model_rebuild(_types_namespace={"Effect": _Effect})
CombatStepOverrides.model_rebuild(_types_namespace={"Effect": _Effect})

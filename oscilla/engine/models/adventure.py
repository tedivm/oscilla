"""Adventure manifest model with event steps and effect types."""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from oscilla.engine.models.base import Condition, ManifestEnvelope

# NOTE: Dict is imported for use in ApplyBuffEffect and DispelEffect.



# ---------------------------------------------------------------------------
# Effects — silent mechanical outcomes (no screen produced)
# ---------------------------------------------------------------------------


class ItemDropEntry(BaseModel):
    item: str
    weight: int = Field(ge=1)


class XpGrantEffect(BaseModel):
    type: Literal["xp_grant"]
    amount: int = Field(description="XP amount; can be negative (penalty) but not zero.")

    @field_validator("amount")
    @classmethod
    def amount_not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("XP amount cannot be zero")
        return v


class ItemDropEffect(BaseModel):
    type: Literal["item_drop"]
    count: int = Field(default=1, ge=1)
    loot: List[ItemDropEntry] = Field(min_length=1)


class MilestoneGrantEffect(BaseModel):
    type: Literal["milestone_grant"]
    milestone: str


class EndAdventureEffect(BaseModel):
    type: Literal["end_adventure"]
    outcome: Literal["completed", "defeated", "fled"] = "completed"


class HealEffect(BaseModel):
    type: Literal["heal"]
    # "full" restores the player to max_hp; a positive integer heals that exact amount.
    amount: int | Literal["full"] = "full"
    # When target is "enemy", requires CombatContext; heal amount is capped at enemy's max_hp
    # which is not tracked — so "full" on an enemy target is treated as a no-op with a warning.
    target: Literal["player", "enemy"] = "player"


class StatChangeEffect(BaseModel):
    type: Literal["stat_change"]
    stat: str = Field(description="Character stat name (player) or ignored when target is 'enemy'.")
    amount: int = Field(description="Amount to add/subtract; can be negative.")
    # When target is "enemy", stat is ignored and amount is applied directly to enemy_hp.
    target: Literal["player", "enemy"] = "player"


class StatSetEffect(BaseModel):
    type: Literal["stat_set"]
    stat: str = Field(description="Character stat name")
    value: int | bool | None = Field(description="New value for stat")
    # target "enemy" is not supported for stat_set — enemies have no named stats.
    target: Literal["player"] = "player"


class UseItemEffect(BaseModel):
    type: Literal["use_item"]
    item: str = Field(description="Item manifest name to use")


class SkillGrantEffect(BaseModel):
    """Permanently teaches a named skill to the player."""

    type: Literal["skill_grant"]
    skill: str = Field(description="Skill manifest name to grant.")


class DispelEffect(BaseModel):
    """Remove all active periodic combat effects matching a given label.

    Matches against ActiveCombatEffect.label. Effects with an empty label are
    never matched (the empty string is explicitly not a wildcard).
    Outside of combat (combat=None) this effect is silently ignored.
    """

    type: Literal["dispel"]
    label: str = Field(min_length=1, description="Label string declared on the PeriodicEffect to remove.")
    target: Literal["player", "enemy"] = Field(
        default="player",
        description="Only effects targeting this participant are removed.",
    )


class ApplyBuffEffect(BaseModel):
    """Apply a named buff from the registry to a combat participant.

    Looks up `buff_ref` in `registry.buffs`, creates an `ActiveCombatEffect` from the
    `BuffSpec`, and appends it to `CombatContext.active_effects`. The buff manifest name
    becomes `ActiveCombatEffect.label` — the same identifier that `DispelEffect` targets.

    Outside of combat (`combat=None`) this effect is silently skipped with a log warning;
    buffs only make sense within the combat turn loop.
    """

    type: Literal["apply_buff"]
    buff_ref: str = Field(description="Buff manifest name to apply.")
    target: Literal["player", "enemy"] = Field(
        default="player",
        description=(
            "Combat participant this buff is applied to. "
            "Defaults to 'player' for self-buffs and enemy-inflicted debuffs; "
            "set to 'enemy' to apply a debuff to the enemy."
        ),
    )
    variables: Dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Per-call overrides for the buff's declared variables. "
            "Merged on top of BuffSpec.variables defaults at apply time. "
            "Unknown keys (not declared in the buff) raise a load-time validation error."
        ),
    )


Effect = Annotated[
    Union[
        XpGrantEffect,
        ItemDropEffect,
        MilestoneGrantEffect,
        EndAdventureEffect,
        HealEffect,
        StatChangeEffect,
        StatSetEffect,
        UseItemEffect,
        SkillGrantEffect,
        DispelEffect,
        ApplyBuffEffect,
    ],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# OutcomeBranch — effects + sub-steps used by all branching events
# ---------------------------------------------------------------------------


class OutcomeBranch(BaseModel):
    """Effects fire first (silent state mutations), then either steps or goto runs."""

    effects: List[Effect] = []
    steps: List["Step"] = []
    goto: str | None = None

    @model_validator(mode="after")
    def goto_and_steps_are_exclusive(self) -> "OutcomeBranch":
        if self.goto is not None and self.steps:
            raise ValueError("OutcomeBranch cannot have both 'goto' and 'steps'.")
        return self


# ---------------------------------------------------------------------------
# Event step types — each produces a player-facing interaction
# ---------------------------------------------------------------------------


class NarrativeStep(BaseModel):
    type: Literal["narrative"]
    label: str | None = None  # goto target identifier; only meaningful at top-level
    text: str = Field(min_length=1)
    effects: List[Effect] = []


class CombatStep(BaseModel):
    type: Literal["combat"]
    label: str | None = None
    enemy: str  # Enemy manifest name
    on_win: OutcomeBranch = Field(default_factory=OutcomeBranch)
    on_defeat: OutcomeBranch = Field(default_factory=OutcomeBranch)
    on_flee: OutcomeBranch = Field(default_factory=OutcomeBranch)


class ChoiceOption(BaseModel):
    label: str  # display label shown to the player
    requires: Condition | None = None
    effects: List[Effect] = []
    steps: List["Step"] = []
    goto: str | None = None

    @model_validator(mode="after")
    def goto_and_steps_are_exclusive(self) -> "ChoiceOption":
        if self.goto is not None and self.steps:
            raise ValueError("ChoiceOption cannot have both 'goto' and 'steps'.")
        return self


class ChoiceStep(BaseModel):
    type: Literal["choice"]
    label: str | None = None
    prompt: str
    options: List[ChoiceOption] = Field(min_length=1)


class StatCheckStep(BaseModel):
    type: Literal["stat_check"]
    label: str | None = None
    condition: Condition
    on_pass: OutcomeBranch = Field(default_factory=OutcomeBranch)
    on_fail: OutcomeBranch = Field(default_factory=OutcomeBranch)


Step = Annotated[
    Union[NarrativeStep, CombatStep, ChoiceStep, StatCheckStep],
    Field(discriminator="type"),
]

# Rebuild all forward-referenced models
OutcomeBranch.model_rebuild()
ChoiceOption.model_rebuild()
ChoiceStep.model_rebuild()
StatCheckStep.model_rebuild()


# ---------------------------------------------------------------------------
# Adventure spec and manifest
# ---------------------------------------------------------------------------


class AdventureSpec(BaseModel):
    displayName: str
    description: str = ""
    requires: Condition | None = None
    steps: List[Step]

    @model_validator(mode="after")
    def validate_unique_labels(self) -> "AdventureSpec":
        """Labels on top-level steps must be unique — they are goto jump targets."""
        seen: Dict[str, int] = {}
        for i, step in enumerate(self.steps):
            lbl = step.label
            if lbl is None:
                continue
            if lbl in seen:
                raise ValueError(f"Duplicate step label {lbl!r} at step indices {seen[lbl]} and {i}.")
            seen[lbl] = i
        # Validate all goto targets resolve to a declared label
        declared = set(seen.keys())
        for step in self.steps:
            self._collect_goto_errors(step, declared)
        return self

    def _collect_goto_errors(self, step: Step, declared: set[str]) -> None:
        """Recursively check that all goto references resolve to a declared label."""
        match step:
            case CombatStep():
                for branch in [step.on_win, step.on_defeat, step.on_flee]:
                    self._check_branch_goto(branch, declared)
            case ChoiceStep():
                for opt in step.options:
                    if opt.goto is not None and opt.goto not in declared:
                        raise ValueError(f"Unresolved goto target {opt.goto!r} in choice option.")
                    for sub in opt.steps:
                        self._collect_goto_errors(sub, declared)
            case StatCheckStep():
                for branch in [step.on_pass, step.on_fail]:
                    self._check_branch_goto(branch, declared)
            case _:
                pass

    def _check_branch_goto(self, branch: OutcomeBranch, declared: set[str]) -> None:
        if branch.goto is not None and branch.goto not in declared:
            raise ValueError(f"Unresolved goto target {branch.goto!r} in outcome branch.")
        for sub in branch.steps:
            self._collect_goto_errors(sub, declared)


class AdventureManifest(ManifestEnvelope):
    kind: Literal["Adventure"]
    spec: AdventureSpec

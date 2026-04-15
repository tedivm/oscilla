"""Adventure manifest model with event steps and effect types."""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Union

from pydantic import BaseModel, Field, model_validator

from oscilla.engine.models.base import Condition, ManifestEnvelope
from oscilla.engine.models.loot_table import LootGroup

# NOTE: Dict is imported for use in ApplyBuffEffect and DispelEffect.


# ---------------------------------------------------------------------------
# Effects — silent mechanical outcomes (no screen produced)
# ---------------------------------------------------------------------------


class ItemDropEffect(BaseModel):
    """Drop items from one or more independent loot groups.

    Exactly one of groups (inline) or loot_ref (named LootTable manifest) must
    be provided. loot_ref is resolved exclusively against registry.loot_tables;
    the historical enemy fallback is removed.
    """

    type: Literal["item_drop"]
    groups: List[LootGroup] | None = Field(
        default=None,
        description="Inline loot group list. Mutually exclusive with loot_ref.",
    )
    loot_ref: str | None = Field(
        default=None,
        description="Reference to a named LootTable manifest. Mutually exclusive with groups.",
    )

    @model_validator(mode="after")
    def exactly_one_loot_source(self) -> "ItemDropEffect":
        has_inline = self.groups is not None and len(self.groups) > 0
        has_ref = self.loot_ref is not None
        if has_inline and has_ref:
            raise ValueError("ItemDropEffect: specify either 'groups' or 'loot_ref', not both.")
        if not has_inline and not has_ref:
            raise ValueError("ItemDropEffect: must specify either 'groups' (inline) or 'loot_ref'.")
        return self


class MilestoneGrantEffect(BaseModel):
    type: Literal["milestone_grant"]
    milestone: str


# Built-in adventure outcome names always accepted without game.yaml declaration.
_BUILTIN_OUTCOMES: frozenset[str] = frozenset({"completed", "defeated", "fled"})


class EndAdventureEffect(BaseModel):
    type: Literal["end_adventure"]
    outcome: str = Field(
        default="completed",
        description=(
            "Outcome name. Built-ins: 'completed', 'defeated', 'fled'. "
            "Custom names must be declared in game.yaml outcomes list."
        ),
    )


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
    # str = template string resolving to int.
    amount: int | str = Field(description="Amount to add/subtract; can be negative or a template string.")
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
    permanent: bool = Field(
        default=False,
        description=(
            "When True, also removes the buff from CharacterState.active_buffs so it does not "
            "re-enter future combats. When False (default), only the in-combat instance is removed."
        ),
    )


class SetPronounsEffect(BaseModel):
    """Assign a named pronoun set to the player.

    The set must be one of the built-in names (they_them, she_her, he_him) or
    a custom name declared in CharacterConfig extra_pronoun_sets.
    """

    type: Literal["set_pronouns"]
    set: str = Field(description="Pronoun set key, e.g. 'they_them', 'she_her', 'he_him', or a custom key.")


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


class QuestActivateEffect(BaseModel):
    type: Literal["quest_activate"]
    quest_ref: str = Field(description="Name of the Quest manifest to activate.")


class QuestFailEffect(BaseModel):
    type: Literal["quest_fail"]
    quest_ref: str = Field(description="Name of the Quest manifest to fail.")


class AdjustGameTicksEffect(BaseModel):
    """Adjust the character's game_ticks by a signed integer delta.

    Positive delta moves the game clock forward; negative moves it backward.
    The internal_ticks counter is never affected by this effect.
    Clamping at zero is controlled by game.time.pre_epoch_behavior.
    """

    type: Literal["adjust_game_ticks"]
    delta: int = Field(description="Signed integer tick adjustment. May be negative.")


class EmitTriggerEffect(BaseModel):
    """Fire a named custom trigger, queuing any registered adventures.

    The trigger name must be declared in game.yaml's triggers.custom list.
    Validated at content load time — unknown names are a load-time warning.
    """

    type: Literal["emit_trigger"]
    trigger: str = Field(description="Custom trigger name declared in game.yaml triggers.custom")


class PrestigeEffect(BaseModel):
    """Reset the character to a new iteration using the prestige config from game.yaml.

    Runs pre_prestige_effects, resets state to character_config defaults, applies
    carry_stats and carry_skills, increments prestige_count, then runs
    post_prestige_effects. Steps after this effect in the same adventure see the
    reset state immediately. The DB transition happens at adventure_end.

    Requires ``prestige:`` to be declared in game.yaml. If absent,
    a ContentLoadError is raised at content load time.
    """

    type: Literal["prestige"]


class SetNameEffect(BaseModel):
    """Prompt the player to enter a name and assign it to the character.

    Always prompts regardless of the character's current name. Use a ``requires``
    condition on the enclosing step when the prompt should be skipped under
    certain circumstances.
    """

    type: Literal["set_name"]
    prompt: str = Field(default="What is your name?", description="Prompt shown to the player.")


class ArchetypeAddEffect(BaseModel):
    """Grant the named archetype to the character.

    Dispatches the archetype's gain_effects on first grant.
    If the archetype is already held and force is False, this is a no-op.
    If force is True, gain_effects are re-dispatched even when already held.
    """

    type: Literal["archetype_add"]
    name: str
    force: bool = False


class ArchetypeRemoveEffect(BaseModel):
    """Remove the named archetype from the character.

    Dispatches the archetype's lose_effects when removed.
    If the archetype is not held and force is False, this is a no-op.
    If force is True, lose_effects are re-dispatched even when not held.
    """

    type: Literal["archetype_remove"]
    name: str
    force: bool = False


class SkillRevokeEffect(BaseModel):
    """Remove the named skill from the character's known skills.

    No-op when the skill is not present — never raises an error.
    """

    type: Literal["skill_revoke"]
    skill: str


Effect = Annotated[
    Union[
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
        SetPronounsEffect,
        QuestActivateEffect,
        QuestFailEffect,
        AdjustGameTicksEffect,
        EmitTriggerEffect,
        PrestigeEffect,
        SetNameEffect,
        ArchetypeAddEffect,
        ArchetypeRemoveEffect,
        SkillRevokeEffect,
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
    requires: Condition | None = None


class CombatStep(BaseModel):
    type: Literal["combat"]
    label: str | None = None
    enemy: str  # Enemy manifest name
    on_win: OutcomeBranch = Field(default_factory=OutcomeBranch)
    on_defeat: OutcomeBranch = Field(default_factory=OutcomeBranch)
    on_flee: OutcomeBranch = Field(default_factory=OutcomeBranch)
    requires: Condition | None = None


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
    requires: Condition | None = None


class StatCheckStep(BaseModel):
    type: Literal["stat_check"]
    label: str | None = None
    condition: Condition
    on_pass: OutcomeBranch = Field(default_factory=OutcomeBranch)
    on_fail: OutcomeBranch = Field(default_factory=OutcomeBranch)
    requires: Condition | None = None


class PassiveStep(BaseModel):
    type: Literal["passive"]
    label: str | None = None
    text: str | None = Field(default=None, description="Narrative text shown when the step fires normally.")
    effects: List[Effect] = Field(default_factory=list, description="Effects applied when the step is not bypassed.")
    bypass: Condition | None = Field(default=None, description="If met, skip the normal text and effects entirely.")
    bypass_text: str | None = Field(
        default=None, description="Shown when bypass condition is met. Omit for silent bypass."
    )
    requires: Condition | None = None


Step = Annotated[
    Union[NarrativeStep, CombatStep, ChoiceStep, StatCheckStep, PassiveStep],
    Field(discriminator="type"),
]

# Rebuild all forward-referenced models
NarrativeStep.model_rebuild()
CombatStep.model_rebuild()
OutcomeBranch.model_rebuild()
ChoiceOption.model_rebuild()
ChoiceStep.model_rebuild()
StatCheckStep.model_rebuild()
PassiveStep.model_rebuild()


# ---------------------------------------------------------------------------
# Adventure spec and manifest
# ---------------------------------------------------------------------------


class Cooldown(BaseModel):
    """Shared cooldown model for adventure repeat controls and skill activation frequency.

    All numeric fields accept int or Jinja2 template strings resolved at eligibility check time.
    Multiple non-None fields are AND-ed — all constraints must pass simultaneously.
    """

    # internal_ticks elapsed since last use — tamper-proof monotone clock.
    ticks: int | str | None = None
    # game_ticks elapsed since last use — narrative clock, adjustable by effects.
    game_ticks: int | str | None = None
    # Real-world seconds elapsed since last use — wall-clock track.
    seconds: int | str | None = None
    # Combat turns before reuse — only valid with scope: "turn".
    turns: int | str | None = None
    # scope: None (default) = persistent across sessions (adventure-scope).
    # scope: "turn" = resets each combat; only "turns" field is evaluated.
    scope: Literal["turn"] | None = None

    @model_validator(mode="after")
    def validate_scope_fields(self) -> "Cooldown":
        if self.scope == "turn":
            if any(v is not None for v in [self.ticks, self.game_ticks, self.seconds]):
                raise ValueError(
                    "Cooldown with scope='turn' may only use 'turns'. Remove ticks, game_ticks, and seconds fields."
                )
        else:
            if self.turns is not None:
                raise ValueError("Cooldown 'turns' field is only valid with scope='turn'.")
        return self

    @model_validator(mode="after")
    def at_least_one_constraint(self) -> "Cooldown":
        if all(v is None for v in [self.ticks, self.game_ticks, self.seconds, self.turns]):
            raise ValueError(
                "Cooldown must specify at least one constraint field (ticks, game_ticks, seconds, or turns)."
            )
        return self


class AdventureSpec(BaseModel):
    displayName: str
    description: str = ""
    requires: Condition | None = None
    steps: List[Step]
    # Tick cost for this adventure. Defaults to game.time.ticks_per_adventure when time
    # is configured, or 1 when time is not configured.
    ticks: int | None = Field(default=None, ge=1, description="Tick cost for this adventure.")
    # Repeat controls — all optional, all default to unrestricted behavior.
    repeatable: bool = Field(default=True, description="Set to False to make this a one-shot adventure.")
    max_completions: int | None = Field(default=None, description="Hard cap on total completions this iteration.")
    # Unified cooldown: ticks, game_ticks, seconds constraints. Replaces flat cooldown_* fields.
    cooldown: Cooldown | None = None

    @model_validator(mode="after")
    def validate_repeat_controls(self) -> "AdventureSpec":
        """repeatable: false and max_completions are mutually exclusive."""
        if not self.repeatable and self.max_completions is not None:
            raise ValueError(
                "AdventureSpec: 'repeatable: false' and 'max_completions' are mutually exclusive. "
                "Use max_completions alone to set a specific cap, or repeatable: false for a one-shot."
            )
        return self

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

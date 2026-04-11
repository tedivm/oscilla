"""Buff manifest model — named, reusable timed combat effects."""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from oscilla.engine.models.adventure import Effect
from oscilla.engine.models.base import ManifestEnvelope


class BuffDuration(BaseModel):
    """Duration control for a buff manifest.

    `turns` is required — the number of combat turns the buff fires per engagement.
    Template strings are accepted and precompiled at load time.

    If none of `ticks`, `game_ticks`, or `seconds` are set, the buff is encounter-scoped
    and is discarded when combat ends.

    If any time-based field is set, the buff is persistent: stored on the player
    and re-injected into each subsequent combat until the expiry conditions are met.
    Multiple time-based fields are AND-ed.
    """

    turns: int | str = Field(ge=1, description="Combat turns the buff persists per encounter.")
    ticks: int | str | None = Field(default=None, description="internal_ticks elapsed before expiry.")
    game_ticks: int | str | None = Field(default=None, description="game_ticks elapsed before expiry.")
    seconds: int | str | None = Field(default=None, description="Real-world seconds before expiry.")

    @property
    def is_persistent(self) -> bool:
        """Return True when any time-based expiry field is set."""
        return any(v is not None for v in (self.ticks, self.game_ticks, self.seconds))


class StoredBuff(BaseModel):
    """A persistent buff carried on CharacterState between combat encounters."""

    buff_ref: str
    remaining_turns: int
    variables: Dict[str, int] = Field(default_factory=dict)
    tick_expiry: int | None = None
    game_tick_expiry: int | None = None
    real_ts_expiry: int | None = None


class DamageReductionModifier(BaseModel):
    """Reduces incoming damage to the named target by a percentage while active."""

    type: Literal["damage_reduction"]
    # int: applied directly (clamped 1–99 to prevent invulnerability exploits).
    # str: variable name resolved against merged variables at apply time.
    percent: int | str = Field(description="Percentage of incoming damage absorbed (1–99), or a buff variable name.")
    target: Literal["player", "enemy"] = Field(
        default="player",
        description="Who receives the damage reduction benefit.",
    )

    @field_validator("percent")
    @classmethod
    def _validate_percent(cls, v: int | str) -> int | str:
        if isinstance(v, int) and not (1 <= v <= 99):
            raise ValueError("percent must be 1–99 when specified as an integer")
        return v


class DamageAmplifyModifier(BaseModel):
    """Increases outgoing damage dealt by the named target by a percentage while active."""

    type: Literal["damage_amplify"]
    # int: applied directly (ge=1); str: variable name resolved at apply time.
    percent: int | str = Field(description="Percentage bonus added to outgoing damage, or a buff variable name.")
    target: Literal["player", "enemy"] = Field(
        default="player",
        description="Who deals amplified damage.",
    )

    @field_validator("percent")
    @classmethod
    def _validate_percent(cls, v: int | str) -> int | str:
        if isinstance(v, int) and v < 1:
            raise ValueError("percent must be >= 1 when specified as an integer")
        return v


class DamageReflectModifier(BaseModel):
    """Reflects a percentage of incoming damage back to the attacker while active."""

    type: Literal["damage_reflect"]
    # int: applied directly (1–100; 100% full reflection is intentional).
    # str: variable name resolved at apply time.
    percent: int | str = Field(
        description="Percentage of damage taken returned to attacker (1–100), or a buff variable name."
    )
    target: Literal["player", "enemy"] = Field(
        default="player",
        description="Who benefits from the reflection (who has the thorns).",
    )

    @field_validator("percent")
    @classmethod
    def _validate_percent(cls, v: int | str) -> int | str:
        if isinstance(v, int) and not (1 <= v <= 100):
            raise ValueError("percent must be 1–100 when specified as an integer")
        return v


class DamageVulnerabilityModifier(BaseModel):
    """Increases incoming damage received by the named target by a percentage while active."""

    type: Literal["damage_vulnerability"]
    # int: applied directly (ge=1); str: variable name resolved at apply time.
    percent: int | str = Field(description="Percentage of bonus damage taken (additive), or a buff variable name.")
    target: Literal["player", "enemy"] = Field(
        default="player",
        description="Who suffers increased incoming damage.",
    )

    @field_validator("percent")
    @classmethod
    def _validate_percent(cls, v: int | str) -> int | str:
        if isinstance(v, int) and v < 1:
            raise ValueError("percent must be >= 1 when specified as an integer")
        return v


# Discriminated union of all passive combat modifiers.
# Use `type` to declare which modifier is intended.
CombatModifier = Annotated[
    Union[
        DamageReductionModifier,
        DamageAmplifyModifier,
        DamageReflectModifier,
        DamageVulnerabilityModifier,
    ],
    Field(discriminator="type"),
]


class BuffSpec(BaseModel):
    """A named, reusable timed combat effect.

    Buffs are declarative: content authors write a `kind: Buff` manifest once and
    reference it by name from any skill, item, or adventure effect that should grant it.
    The manifest name is the buff's stable identity — it is used as the `label` on any
    resulting `ActiveCombatEffect`, and by `DispelEffect` to remove the effect early.

    Must declare at least one of `per_turn_effects` (discrete tick effects dispatched
    each round) or `modifiers` (passive damage-arithmetic adjustments). Both may be
    combined for effects such as a burn that deals tick damage *and* increases damage taken.
    """

    displayName: str
    description: str = ""
    # NOTE: No target field — target is specified on ApplyBuffEffect at use time,
    # allowing the same buff manifest to be applied to either player or enemy.
    duration: BuffDuration = Field(description="Duration and persistence settings for this buff.")
    per_turn_effects: List[Effect] = Field(
        default_factory=list,
        description=(
            "Effects dispatched at the start of each tick. "
            "May be empty when the buff is purely modifier-based (e.g. a shield or rage buff)."
        ),
    )
    modifiers: List[CombatModifier] = Field(
        default_factory=list,
        description=(
            "Passive modifiers applied to damage arithmetic while this buff is active. "
            "Unlike per_turn_effects, these are not dispatched as discrete effects — "
            "the combat loop queries them during attack and defence calculations. "
            "Modifier percent fields may be int or a variable name from `variables`."
        ),
    )
    variables: Dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Named integer parameters with default values. "
            "Modifier percent fields may reference these by name instead of hardcoding a value. "
            "Call sites (ApplyBuffEffect, BuffGrant) may override individual keys."
        ),
    )
    # Exclusion group: buffs sharing the same group name compete against each other.
    # A new application is blocked when an equal-or-higher priority entry is already active.
    exclusion_group: str | None = Field(
        default=None,
        description="Group name used for priority-based exclusion. Buffs with the same group compete.",
    )
    # priority: int for a fixed value; str to name a variable in `variables` resolved at apply time.
    # Only meaningful when exclusion_group is set.
    priority: int | str = Field(
        default=0,
        description="Priority value for exclusion checks. Higher priority beats lower.",
    )
    # Controls whether a stronger incoming buff evicts existing weaker entries.
    exclusion_mode: Literal["block", "replace"] = Field(
        default="block",
        description=(
            "'block': existing lower-priority entries expire naturally when a stronger buff is applied. "
            "'replace': existing lower-priority entries are removed when a stronger buff is applied."
        ),
    )

    @model_validator(mode="after")
    def require_tick_or_modifier(self) -> "BuffSpec":
        """At least one of per_turn_effects or modifiers must be non-empty."""
        if not self.per_turn_effects and not self.modifiers:
            raise ValueError("BuffSpec must declare at least one per_turn_effect or modifier.")
        return self

    @model_validator(mode="after")
    def validate_variable_refs(self) -> "BuffSpec":
        """Ensure all string percent refs in modifiers and string priority are declared in variables."""
        import logging

        _log = logging.getLogger(__name__)
        declared = set(self.variables.keys())
        for mod in self.modifiers:
            if isinstance(mod.percent, str) and mod.percent not in declared:
                raise ValueError(f"Modifier references variable {mod.percent!r} which is not declared in variables.")
        # Validate string priority refers to a declared variable.
        if isinstance(self.priority, str) and self.priority not in declared:
            raise ValueError(f"BuffSpec priority references variable {self.priority!r} which is not declared.")
        # Warn when priority is non-zero but no exclusion_group is set.
        if self.priority != 0 and self.exclusion_group is None:
            _log.warning(
                "BuffSpec has priority=%r but no exclusion_group — priority has no effect without a group.",
                self.priority,
            )
        return self


class BuffManifest(ManifestEnvelope):
    kind: Literal["Buff"]
    spec: BuffSpec

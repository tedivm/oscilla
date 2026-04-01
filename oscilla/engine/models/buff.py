"""Buff manifest model — named, reusable timed combat effects."""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from oscilla.engine.models.adventure import Effect
from oscilla.engine.models.base import ManifestEnvelope


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
    duration_turns: int = Field(ge=1, description="Number of combat turns this buff persists.")
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

    @model_validator(mode="after")
    def require_tick_or_modifier(self) -> "BuffSpec":
        """At least one of per_turn_effects or modifiers must be non-empty."""
        if not self.per_turn_effects and not self.modifiers:
            raise ValueError("BuffSpec must declare at least one per_turn_effect or modifier.")
        return self

    @model_validator(mode="after")
    def validate_variable_refs(self) -> "BuffSpec":
        """Ensure all string percent refs in modifiers are declared in variables."""
        declared = set(self.variables.keys())
        for mod in self.modifiers:
            if isinstance(mod.percent, str) and mod.percent not in declared:
                raise ValueError(f"Modifier references variable {mod.percent!r} which is not declared in variables.")
        return self


class BuffManifest(ManifestEnvelope):
    kind: Literal["Buff"]
    spec: BuffSpec

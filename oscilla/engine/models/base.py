"""Base manifest envelope and shared condition models.

All manifest kinds share the same apiVersion/kind/metadata/spec envelope.
Condition models are defined here and imported by other manifest modules.
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Union

from pydantic import BaseModel, Field, model_validator


class Metadata(BaseModel):
    name: str = Field(description="Unique identifier for this entity within its kind.")


class ManifestEnvelope(BaseModel):
    apiVersion: Literal["game/v1"]
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


class MilestoneCondition(BaseModel):
    type: Literal["milestone"]
    name: str


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
    type: Literal["iteration"]
    gt: int | None = None
    gte: int | None = None
    lt: int | None = None
    lte: int | None = None
    eq: int | None = None
    mod: ModComparison | None = None

    @model_validator(mode="after")
    def require_comparator(self) -> "PrestigeCountCondition":
        if all(v is None for v in [self.gt, self.gte, self.lt, self.lte, self.eq, self.mod]):
            raise ValueError("iteration condition must specify at least one of: gt, gte, lt, lte, eq, mod")
        return self


class ClassCondition(BaseModel):
    type: Literal["class"]
    name: str  # always evaluates True in v1


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
    ],
    Field(discriminator="type"),
]

AllCondition.model_rebuild()
AnyCondition.model_rebuild()
NotCondition.model_rebuild()

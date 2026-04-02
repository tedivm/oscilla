"""Base manifest envelope and shared condition models.

All manifest kinds share the same apiVersion/kind/metadata/spec envelope.
Condition models are defined here and imported by other manifest modules.
"""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Union

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


class CharacterStatCondition(BaseModel):
    type: Literal["character_stat"]
    name: str
    gt: int | float | None = None
    gte: int | float | None = None
    lt: int | float | None = None
    lte: int | float | None = None
    eq: int | float | None = None
    mod: ModComparison | None = None

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


# ---------------------------------------------------------------------------
# YAML → Python normalisation
# Converts bare YAML condition keys like {level: 3} to {type: level, value: 3}
# so Pydantic's discriminated union can dispatch correctly.
# ---------------------------------------------------------------------------

_LEAF_MAPPINGS: dict[str, tuple[str, str]] = {
    # key → (type_value, value_key_in_model)
    "level": ("level", "value"),
    "milestone": ("milestone", "name"),
    "item": ("item", "name"),
    "class": ("class", "name"),
    "pronouns": ("pronouns", "set"),
}

# Keys whose value is already the full sub-dict (not a scalar)
_DICT_LEAVES: set[str] = {
    "character_stat",
    "iteration",
    "enemies_defeated",
    "locations_visited",
    "adventures_completed",
    "skill",
}

# Branch keys whose sub-conditions need recursive normalisation
_BRANCH_KEYS: set[str] = {"all", "any", "not"}


def normalise_condition(raw: object) -> Dict[str, object]:
    """Convert bare YAML condition dict to the type-tagged form Pydantic expects.

    Examples:
        {"level": 3}            → {"type": "level",     "value": 3}
        {"milestone": "found"}  → {"type": "milestone", "name": "found"}
        {"all": [...]}          → {"type": "all",        "conditions": [...]}
        {"character_stat": {…}} → {"type": "character_stat", "name": …, …}

    Raises ValueError if the dict contains more than one recognised key or
    if the input is not a dict.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"Condition must be a mapping, got {type(raw).__name__!r}")

    # Already normalised (has a 'type' key)
    if "type" in raw:
        return raw

    recognised = [k for k in raw if k in _LEAF_MAPPINGS or k in _DICT_LEAVES or k in _BRANCH_KEYS]
    if len(recognised) == 0:
        raise ValueError(f"Unrecognised condition key(s): {list(raw.keys())!r}")
    if len(recognised) > 1:
        raise ValueError(
            f"Condition dict has multiple keys {recognised!r}; each condition must contain exactly one semantic key."
        )

    key = recognised[0]

    if key in _BRANCH_KEYS:
        value = raw[key]
        if key == "not":
            return {"type": "not", "condition": normalise_condition(value)}
        # "all" / "any" — value is a list of sub-conditions
        if not isinstance(value, list):
            raise ValueError(f"'{key}' condition value must be a list, got {type(value).__name__!r}")
        return {"type": key, "conditions": [normalise_condition(c) for c in value]}

    if key in _LEAF_MAPPINGS:
        _type, value_key = _LEAF_MAPPINGS[key]
        return {"type": _type, value_key: raw[key]}

    # _DICT_LEAVES: value is already a sub-dict; merge type in
    sub = dict(raw[key])
    sub["type"] = key
    return sub

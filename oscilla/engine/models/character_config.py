"""CharacterConfig manifest — defines all player stats for a content package."""

from typing import List, Literal, Set

from pydantic import BaseModel, model_validator

from oscilla.engine.models.base import Condition, ManifestEnvelope

StatType = Literal["int", "bool"]


class StatBounds(BaseModel):
    """Inclusive bounds for an integer stat. Either bound may be omitted (defaults to INT64 range)."""

    min: int | None = None
    max: int | None = None

    @model_validator(mode="after")
    def validate_min_lte_max(self) -> "StatBounds":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"StatBounds.min ({self.min}) must be less than or equal to StatBounds.max ({self.max})")
        return self


class StatDefinition(BaseModel):
    name: str
    type: StatType
    default: int | bool | None = None
    description: str = ""
    bounds: StatBounds | None = None

    @model_validator(mode="after")
    def validate_bounds_not_on_bool(self) -> "StatDefinition":
        if self.type == "bool" and self.bounds is not None:
            raise ValueError(f"StatBounds cannot be set on a bool stat (stat name: {self.name!r})")
        return self


class SlotDefinition(BaseModel):
    name: str
    displayName: str
    # Item categories that can be equipped in this slot (empty = no restriction)
    accepts: List[str] = []
    # Condition that must pass before this slot is unlocked; None = always unlocked
    requires: Condition | None = None
    show_when_locked: bool = False


class CharacterConfigSpec(BaseModel):
    public_stats: List[StatDefinition] = []
    hidden_stats: List[StatDefinition] = []
    equipment_slots: List[SlotDefinition] = []

    @model_validator(mode="after")
    def validate_unique_stat_names(self) -> "CharacterConfigSpec":
        all_names = [s.name for s in self.public_stats] + [s.name for s in self.hidden_stats]
        seen: Set[str] = set()
        duplicates: List[str] = []
        for name in all_names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)
        if duplicates:
            raise ValueError(
                f"Duplicate stat names in CharacterConfig: {sorted(set(duplicates))!r}. "
                "Each stat name must be unique across public_stats and hidden_stats."
            )
        return self

    @model_validator(mode="after")
    def validate_unique_slot_names(self) -> "CharacterConfigSpec":
        seen_slots: Set[str] = set()
        duplicates: List[str] = []
        for slot in self.equipment_slots:
            if slot.name in seen_slots:
                duplicates.append(slot.name)
            seen_slots.add(slot.name)
        if duplicates:
            raise ValueError(
                f"Duplicate slot names in CharacterConfig: {sorted(set(duplicates))!r}. Each slot name must be unique."
            )
        return self


class CharacterConfigManifest(ManifestEnvelope):
    kind: Literal["CharacterConfig"]
    spec: CharacterConfigSpec

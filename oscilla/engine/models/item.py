"""Item manifest model."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, model_validator

from oscilla.engine.models.adventure import Effect
from oscilla.engine.models.base import ManifestEnvelope


class StatModifier(BaseModel):
    stat: str
    amount: int | float


class EquipSpec(BaseModel):
    slots: List[str] = Field(min_length=1)
    stat_modifiers: List[StatModifier] = []


class ItemSpec(BaseModel):
    category: str
    displayName: str
    description: str = ""
    use_effects: List[Effect] = []
    consumed_on_use: bool = True
    equip: EquipSpec | None = None
    stackable: bool = True
    droppable: bool = True
    value: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_stackable_equip(self) -> "ItemSpec":
        if self.stackable and self.equip is not None:
            raise ValueError(
                "An item cannot be both stackable and equippable. Set stackable: false to use an equip spec."
            )
        return self


class ItemManifest(ManifestEnvelope):
    kind: Literal["Item"]
    spec: ItemSpec

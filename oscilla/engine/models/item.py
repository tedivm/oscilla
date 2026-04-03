"""Item manifest model."""

from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field, model_validator

from oscilla.engine.models.adventure import Effect
from oscilla.engine.models.base import Condition, ManifestEnvelope


class StatModifier(BaseModel):
    stat: str
    amount: int | float


class EquipSpec(BaseModel):
    slots: List[str] = Field(min_length=1)
    stat_modifiers: List[StatModifier] = []
    # Optional prerequisite condition evaluated before allowing equip.
    # When stat_source is "effective", the item's own bonuses are excluded
    # from the check to prevent self-justification.
    requires: Condition | None = None


class BuffGrant(BaseModel):
    """A reference to a Buff manifest with optional per-call variable overrides.

    Used in ItemSpec.grants_buffs_equipped and grants_buffs_held to allow the
    same buff manifest to be applied with item-specific parameters (e.g. a
    master-thorns-sword that reflects 60% instead of the default 30%).
    """

    buff_ref: str = Field(description="Buff manifest name to apply.")
    variables: Dict[str, int] = Field(
        default_factory=dict,
        description="Variable overrides applied on top of the buff's declared defaults.",
    )


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
    # Author-assigned classification tags for display and condition evaluation.
    labels: List[str] = []
    # Maximum number of uses before the instance is removed (non-stackable only).
    # Mutually exclusive with consumed_on_use: true and stackable: true.
    charges: int | None = None
    # Skills granted only while this item occupies an equipment slot.
    grants_skills_equipped: List[str] = []
    # Skills granted while this item is anywhere in inventory (stacks or instances).
    grants_skills_held: List[str] = []
    # Buff grants applied at the start of each combat while this item occupies an equipment slot.
    grants_buffs_equipped: List[BuffGrant] = []
    # Buff grants applied at the start of each combat while this item is anywhere in inventory.
    grants_buffs_held: List[BuffGrant] = []

    @model_validator(mode="after")
    def validate_stackable_equip(self) -> "ItemSpec":
        if self.stackable and self.equip is not None:
            raise ValueError(
                "An item cannot be both stackable and equippable. Set stackable: false to use an equip spec."
            )
        return self

    @model_validator(mode="after")
    def validate_charges(self) -> "ItemSpec":
        if self.charges is not None:
            if self.consumed_on_use:
                raise ValueError(
                    "An item cannot have both 'charges' and 'consumed_on_use: true'. "
                    "These are mutually exclusive consumption systems."
                )
            if self.stackable:
                raise ValueError(
                    "An item cannot have 'charges' and be stackable. Charge tracking requires per-instance state."
                )
        return self


class ItemManifest(ManifestEnvelope):
    kind: Literal["Item"]
    spec: ItemSpec

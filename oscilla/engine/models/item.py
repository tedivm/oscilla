"""Item manifest model."""

from typing import Dict, Literal, Union

from pydantic import BaseModel, Field

from oscilla.engine.models.base import ManifestEnvelope

ItemKind = Literal["consumable", "weapon", "armor", "accessory", "quest", "material", "currency", "prestige"]


class ItemSpec(BaseModel):
    displayName: str
    description: str = ""
    kind: ItemKind
    slot: str | None = None  # equipment slot (weapon, armor, etc.)
    stats: Dict[str, int | float] = {}
    effect: Dict[str, Union[int, float, str, bool]] = {}  # item use effect dict (e.g. {heal: 30})
    stackable: bool = True
    droppable: bool = True
    value: int = Field(default=0, ge=0)


class ItemManifest(ManifestEnvelope):
    kind: Literal["Item"]
    spec: ItemSpec

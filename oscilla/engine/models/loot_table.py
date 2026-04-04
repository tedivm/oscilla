"""LootTable manifest model — named, reusable loot definitions."""

from typing import List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import ManifestEnvelope


class LootEntry(BaseModel):
    """A single weighted entry in a loot table.

    `quantity` controls how many of the item are added when this entry is
    selected. Weight is relative to other entries in the same table.
    """

    item: str
    weight: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1)


class LootTableSpec(BaseModel):
    displayName: str
    description: str = ""
    loot: List[LootEntry] = Field(min_length=1)


class LootTableManifest(ManifestEnvelope):
    kind: Literal["LootTable"]
    spec: LootTableSpec

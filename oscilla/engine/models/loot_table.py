"""LootTable manifest model — named, reusable loot definitions."""

from typing import List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import BaseSpec, Condition, ManifestEnvelope


class LootEntry(BaseModel):
    """A single weighted entry within a LootGroup.

    weight: relative draw probability in weighted mode; ignored in unique mode.
    amount: how many of the item to grant per selection. Template-capable (int | str).
    requires: optional condition evaluated at runtime; entry is excluded from the
              pool when it evaluates False. A None condition always passes.
    """

    item: str
    weight: int = Field(default=1, ge=1)
    amount: int | str = Field(default=1)
    requires: Condition | None = None


class LootGroup(BaseModel):
    """An independent draw pool within a loot table.

    count: how many entries to draw from this group. Template-capable (int | str).
    method: "weighted" (default) draws with replacement using entry weights;
            "unique" draws without replacement via random.sample (weights ignored,
            count clamped to pool size).
    requires: optional condition evaluated at runtime; the entire group is skipped
              when it evaluates False.
    entries: at least one LootEntry required.
    """

    count: int | str = Field(default=1)
    method: Literal["weighted", "unique"] = "weighted"
    requires: Condition | None = None
    entries: List[LootEntry] = Field(min_length=1)


class LootTableSpec(BaseSpec):
    displayName: str
    description: str = ""
    groups: List[LootGroup] = Field(min_length=1)


class LootTableManifest(ManifestEnvelope):
    kind: Literal["LootTable"]
    spec: LootTableSpec

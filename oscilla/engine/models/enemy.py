"""Enemy manifest model."""

from typing import List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import ManifestEnvelope


class LootEntry(BaseModel):
    item: str
    weight: int = Field(ge=1)


class EnemySpec(BaseModel):
    displayName: str
    description: str = ""
    hp: int = Field(ge=1)
    attack: int = Field(ge=0)
    defense: int = Field(ge=0)
    xp_reward: int = Field(ge=0)
    loot: List[LootEntry] = []


class EnemyManifest(ManifestEnvelope):
    kind: Literal["Enemy"]
    spec: EnemySpec

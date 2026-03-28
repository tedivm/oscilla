"""Game manifest — global settings for a content package."""

from typing import List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import ManifestEnvelope


class HpFormula(BaseModel):
    base_hp: int = Field(ge=1)
    hp_per_level: int = Field(ge=0)


class GameSpec(BaseModel):
    displayName: str
    description: str = ""
    # XP required to reach each level. Index 0 = XP to reach level 2, etc.
    xp_thresholds: List[int] = Field(min_length=1)
    hp_formula: HpFormula
    base_adventure_count: int | None = None  # null = unlimited


class GameManifest(ManifestEnvelope):
    kind: Literal["Game"]
    spec: GameSpec

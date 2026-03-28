"""Location manifest model."""

from typing import List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import Condition, ManifestEnvelope


class AdventurePoolEntry(BaseModel):
    ref: str  # Adventure manifest name
    weight: int = Field(ge=1)
    requires: Condition | None = None


class LocationSpec(BaseModel):
    displayName: str
    description: str = ""
    region: str  # Region manifest name
    unlock: Condition | None = None
    adventures: List[AdventurePoolEntry] = []
    # Compiled at load time by build_effective_conditions(); not in YAML.
    effective_unlock: Condition | None = None


class LocationManifest(ManifestEnvelope):
    kind: Literal["Location"]
    spec: LocationSpec

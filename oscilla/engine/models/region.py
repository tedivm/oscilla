"""Region manifest model."""

from typing import Literal

from pydantic import BaseModel

from oscilla.engine.models.base import Condition, ManifestEnvelope


class RegionSpec(BaseModel):
    displayName: str
    description: str = ""
    parent: str | None = None  # metadata.name of parent Region
    unlock: Condition | None = None
    # Compiled at load time by build_effective_conditions(); not in YAML.
    effective_unlock: Condition | None = None


class RegionManifest(ManifestEnvelope):
    kind: Literal["Region"]
    spec: RegionSpec

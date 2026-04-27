"""Region manifest model."""

from typing import Literal

from oscilla.engine.models.base import BaseSpec, Condition, ManifestEnvelope


class RegionSpec(BaseSpec):
    displayName: str
    description: str = ""
    parent: str | None = None  # metadata.name of parent Region
    unlock: Condition | None = None
    # Compiled at load time by build_effective_conditions(); not in YAML.
    effective_unlock: Condition | None = None


class RegionManifest(ManifestEnvelope):
    kind: Literal["Region"]
    spec: RegionSpec

"""Character class manifest — placeholder for v1."""

from typing import Literal

from pydantic import BaseModel

from oscilla.engine.models.base import ManifestEnvelope


class ClassSpec(BaseModel):
    displayName: str
    description: str = ""
    primary_stat: str | None = None  # stat name from CharacterConfig


class ClassManifest(ManifestEnvelope):
    kind: Literal["Class"]
    spec: ClassSpec

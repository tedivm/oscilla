"""Pydantic models for the CustomCondition manifest kind."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from oscilla.engine.models.base import Condition, ManifestEnvelope


class CustomConditionSpec(BaseModel):
    display_name: str | None = None
    # The stored condition body. Typed as Condition but imported via TYPE_CHECKING to
    # avoid a circular import: base.py's Condition union will include CustomConditionRef,
    # which is declared before this module is first imported.
    condition: Condition


class CustomConditionManifest(ManifestEnvelope):
    kind: Literal["CustomCondition"]
    spec: CustomConditionSpec


# Condition is a forward-referenced union in base.py; rebuild to resolve it.
CustomConditionSpec.model_rebuild()
CustomConditionManifest.model_rebuild()

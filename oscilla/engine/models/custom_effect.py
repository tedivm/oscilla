"""Pydantic models for the CustomEffect manifest kind."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal

from pydantic import BaseModel, Field, model_validator

from oscilla.engine.models.base import BaseSpec, ManifestEnvelope

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import Effect


# NOTE: CustomEffectRef is defined in adventure.py to avoid circular import issues
# (Effect union includes CustomEffectRef, and CustomEffectSpec.effects references Effect).


class CustomEffectParameter(BaseModel):
    """A typed parameter for a CustomEffect manifest."""

    name: str = Field(description="Parameter name, used as key in params dict and 'params' template variable.")
    type: Literal["int", "float", "str", "bool"] = Field(description="Parameter type for validation.")
    default: int | float | str | bool | None = Field(
        default=None,
        description="Default value. If None, the caller must supply this parameter.",
    )


class CustomEffectSpec(BaseSpec):
    """Spec block for a CustomEffect manifest.

    Custom effects are named, parameterized sequences of standard effects.
    Authors declare a parameter schema and an effect body. At call sites,
    `type: custom_effect` references the manifest by name and supplies
    per-call parameter overrides.
    """

    displayName: str | None = None
    description: str = ""
    parameters: List[CustomEffectParameter] = Field(
        default_factory=list,
        description="Typed parameter schema for this custom effect.",
    )
    effects: List["Effect"] = Field(
        min_length=1,
        description=("Effect body. Standard effects and nested custom effects are both allowed."),
    )

    @model_validator(mode="after")
    def validate_unique_param_names(self) -> "CustomEffectSpec":
        names = [p.name for p in self.parameters]
        if len(names) != len(set(names)):
            dupes = {n for n in names if names.count(n) > 1}
            raise ValueError(f"CustomEffect parameters must have unique names, duplicates: {dupes}")
        return self


class CustomEffectManifest(ManifestEnvelope):
    kind: Literal["CustomEffect"]
    spec: CustomEffectSpec


# NOTE: model_rebuild() is called from adventure.py after the Effect union is fully
# defined, to avoid circular import issues.

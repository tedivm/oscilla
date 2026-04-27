"""Recipe manifest model."""

from typing import List, Literal

from pydantic import BaseModel, Field

from oscilla.engine.models.base import BaseSpec, ManifestEnvelope


class RecipeIngredient(BaseModel):
    item: str
    quantity: int = Field(ge=1)


class RecipeOutput(BaseModel):
    item: str
    quantity: int = Field(default=1, ge=1)


class RecipeSpec(BaseSpec):
    displayName: str
    description: str = ""
    inputs: List[RecipeIngredient] = Field(min_length=1)
    output: RecipeOutput


class RecipeManifest(ManifestEnvelope):
    kind: Literal["Recipe"]
    spec: RecipeSpec

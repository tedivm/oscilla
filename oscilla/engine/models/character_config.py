"""CharacterConfig manifest — defines all player stats for a content package."""

from typing import List, Literal, Set

from pydantic import BaseModel, model_validator

from oscilla.engine.models.base import ManifestEnvelope

StatType = Literal["int", "float", "str", "bool"]


class StatDefinition(BaseModel):
    name: str
    type: StatType
    default: int | float | str | bool | None = None
    description: str = ""


class CharacterConfigSpec(BaseModel):
    public_stats: List[StatDefinition] = []
    hidden_stats: List[StatDefinition] = []

    @model_validator(mode="after")
    def validate_unique_stat_names(self) -> "CharacterConfigSpec":
        all_names = [s.name for s in self.public_stats] + [s.name for s in self.hidden_stats]
        seen: Set[str] = set()
        duplicates: List[str] = []
        for name in all_names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)
        if duplicates:
            raise ValueError(
                f"Duplicate stat names in CharacterConfig: {sorted(set(duplicates))!r}. "
                "Each stat name must be unique across public_stats and hidden_stats."
            )
        return self


class CharacterConfigManifest(ManifestEnvelope):
    kind: Literal["CharacterConfig"]
    spec: CharacterConfigSpec

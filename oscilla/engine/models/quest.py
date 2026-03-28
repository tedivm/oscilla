"""Quest manifest model with stage graph validation."""

from typing import List, Literal, Set

from pydantic import BaseModel, model_validator

from oscilla.engine.models.base import ManifestEnvelope


class QuestStage(BaseModel):
    name: str
    description: str = ""
    advance_on: List[str] = []  # milestone names that trigger advancement
    next_stage: str | None = None  # None only for terminal stages
    terminal: bool = False  # True = quest complete at this stage


class QuestSpec(BaseModel):
    displayName: str
    description: str = ""
    entry_stage: str
    stages: List[QuestStage]

    @model_validator(mode="after")
    def validate_stage_graph(self) -> "QuestSpec":
        stage_names: List[str] = [s.name for s in self.stages]
        seen: Set[str] = set()
        for name in stage_names:
            if name in seen:
                raise ValueError(f"Duplicate quest stage name: {name!r}")
            seen.add(name)

        if self.entry_stage not in seen:
            raise ValueError(f"entry_stage {self.entry_stage!r} is not a defined stage.")

        for stage in self.stages:
            if stage.terminal:
                if stage.next_stage is not None:
                    raise ValueError(f"Stage {stage.name!r} is terminal but has next_stage={stage.next_stage!r}")
                if stage.advance_on:
                    raise ValueError(f"Stage {stage.name!r} is terminal but has advance_on={stage.advance_on!r}")
            else:
                if stage.next_stage is None:
                    raise ValueError(f"Stage {stage.name!r} is not terminal but has no next_stage")
                if stage.next_stage not in seen:
                    raise ValueError(f"Stage {stage.name!r} → next_stage={stage.next_stage!r} is not a defined stage")
        return self


class QuestManifest(ManifestEnvelope):
    kind: Literal["Quest"]
    spec: QuestSpec

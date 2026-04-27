"""Quest manifest model with stage graph validation."""

from typing import TYPE_CHECKING, List, Literal, Set

from pydantic import BaseModel, model_validator

from oscilla.engine.models.base import BaseSpec, Condition, ManifestEnvelope

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import Effect


class QuestStage(BaseModel):
    name: str
    description: str = ""
    advance_on: List[str] = []  # milestone names that trigger advancement
    next_stage: str | None = None  # None only for terminal stages
    terminal: bool = False  # True = quest complete at this stage
    # Effects fired when this stage is reached AND it is terminal.
    # Enforced by model_validator: non-terminal stages must have an empty list.
    completion_effects: List["Effect"] = []
    # Failure condition evaluated after every milestone grant. If it fires while
    # the quest is active at this stage, the quest is moved to failed_quests.
    # Terminal stages must not declare a fail_condition (they are already done).
    fail_condition: Condition | None = None
    # Effects fired when this stage's fail_condition triggers. No-op for silent failure.
    fail_effects: List["Effect"] = []


class QuestSpec(BaseSpec):
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
                # Terminal stages cannot have a fail_condition — the quest is already done.
                if stage.fail_condition is not None:
                    raise ValueError(f"Stage {stage.name!r} is terminal and must not have a fail_condition.")
            else:
                if stage.next_stage is None:
                    raise ValueError(f"Stage {stage.name!r} is not terminal but has no next_stage")
                if stage.next_stage not in seen:
                    raise ValueError(f"Stage {stage.name!r} → next_stage={stage.next_stage!r} is not a defined stage")
                # Non-terminal stages must not declare completion_effects — those only
                # fire when the quest is done; putting effects on intermediate stages
                # would mislead authors into thinking they fire at mid-stage entrance.
                if stage.completion_effects:
                    raise ValueError(
                        f"Stage {stage.name!r} is not terminal but has completion_effects. "
                        "completion_effects are only valid on terminal stages."
                    )
        return self


class QuestManifest(ManifestEnvelope):
    kind: Literal["Quest"]
    spec: QuestSpec


# Resolve forward reference to Effect after the adventure module is fully loaded.
from oscilla.engine.models.adventure import Effect  # noqa: E402

QuestStage.model_rebuild()

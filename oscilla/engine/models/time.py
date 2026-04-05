"""In-game time system manifest models.

All models are Pydantic BaseModel subclasses following the same conventions
as the rest of oscilla/engine/models/. Loaded via GameSpec.time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Dict, List, Literal, Union

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from oscilla.engine.models.base import Condition


class RootCycleSpec(BaseModel):
    """The atomic tick unit. Exactly one root cycle is allowed per game.

    A root cycle represents the smallest indivisible time unit — one tick equals
    one game-time step. count is always 1; there are no sub-tick subdivisions and
    no display labels. All named display cycles (hours, moon phases, seasons, etc.)
    must be DerivedCycleSpec entries with a parent reference.

    aliases: additional names that resolve to this cycle in parent references,
             epoch specifications, and condition cycle fields.
    """

    type: Literal["ticks"]
    name: str
    count: Literal[1] = 1
    aliases: List[str] = Field(default_factory=list)


class DerivedCycleSpec(BaseModel):
    """A cycle derived from a parent cycle.

    parent: name or alias of the parent cycle.
    count: how many parent units make one of this unit (e.g. 7 days per week).
    labels: optional display names. Must have exactly count entries if supplied.
    """

    type: Literal["cycle"]
    name: str
    parent: str
    count: int = Field(ge=1)
    labels: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_labels(self) -> "DerivedCycleSpec":
        if self.labels and len(self.labels) != self.count:
            raise ValueError(
                f"DerivedCycleSpec {self.name!r}: labels list has {len(self.labels)} entries "
                f"but count is {self.count}. They must match exactly."
            )
        return self


CycleSpec = Annotated[Union[RootCycleSpec, DerivedCycleSpec], Field(discriminator="type")]


class EraSpec(BaseModel):
    """A named counter that tracks the number of completed cycles of a given type.

    name: unique identifier for this era (used in conditions and templates).
    format: Python str.format-style string with a {count} variable.
            Example: "{count} AC" produces "298 AC".
    epoch_count: the counter value at the moment of era activation (the first tick
                 the era is active). For always-active eras (no start_condition),
                 this is the value at tick 0. Default: 1.
    tracks: the cycle name whose completions increment the counter.
            Must reference a cycle declared in time.cycles.
    start_condition: fires at most once. When first true, the era activates and
                     current game_ticks is recorded as era_started_at_ticks.
                     When absent, the era is always active from tick 0.
    end_condition: fires at most once after the era activates. When first true,
                   the era deactivates and current game_ticks is recorded as
                   era_ended_at_ticks. When absent, the era never ends.
    """

    name: str
    format: str = Field(description='Format string with {count} variable. Example: "{count} AC"')
    epoch_count: int = Field(default=1)
    tracks: str
    start_condition: "Condition | None" = None
    end_condition: "Condition | None" = None


class GameTimeSpec(BaseModel):
    """Top-level in-game time configuration block in game.yaml spec.time.

    epoch is a plain mapping of cycle-name (or alias) to label string or 1-based
    integer index. YAML authors write it as flat keys:

        epoch:
          month: March
          day: 15

    Pydantic parses this naturally as dict[str, int | str]. Semantic validation
    resolves cycle names and validates label values.
    """

    ticks_per_adventure: int = Field(default=1, ge=1)
    base_unit: str = Field(default="tick", description="Display label for one tick.")
    pre_epoch_behavior: Literal["clamp", "allow"] = "clamp"
    cycles: List[CycleSpec] = Field(default_factory=list)
    # Flat mapping of cycle-name → label or 1-based integer. Empty dict = no epoch shift.
    epoch: Dict[str, int | str] = Field(default_factory=dict)
    eras: List[EraSpec] = Field(default_factory=list)


# Rebuild EraSpec now that Condition is importable from base (avoids circular import
# at module load time; EraSpec.start_condition / end_condition use forward refs).
from oscilla.engine.models.base import Condition  # noqa: E402

EraSpec.model_rebuild()

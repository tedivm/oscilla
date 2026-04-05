"""In-game time resolver.

Converts raw tick counters (internal_ticks, game_ticks) into human-readable
calendar state using the game's configured time system.

The resolver is constructed once per registry load. It holds the pre-computed
epoch_offset (number of ticks to add to game_ticks before computing cycle
positions) and the resolved ticks_per_cycle map.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from oscilla.engine.character import CharacterState
    from oscilla.engine.models.time import DerivedCycleSpec, GameTimeSpec, RootCycleSpec
    from oscilla.engine.registry import ContentRegistry

logger = getLogger(__name__)


@dataclass(frozen=True)
class CycleState:
    """Resolved state for a single cycle at a given tick value."""

    name: str
    position: int  # 0-based index within the cycle
    label: str  # display label; "Name N" if no labels declared


@dataclass(frozen=True)
class EraState:
    """Resolved state for a single era at a given tick value."""

    name: str
    # epoch_count + completed full tracked cycles since era activation.
    # Equals epoch_count on the first tick the era is active.
    # Not meaningful when active is False and the era has never started.
    count: int
    active: bool


@dataclass(frozen=True)
class InGameTimeView:
    """Fully resolved in-game time state for a single tick snapshot.

    Exposed as ingame_time in the template ExpressionContext.
    Used by the condition evaluator for all three game_calendar_* predicates.
    """

    internal_ticks: int
    game_ticks: int
    cycles: Dict[str, CycleState] = field(default_factory=dict)
    eras: Dict[str, EraState] = field(default_factory=dict)

    def cycle(self, name: str) -> CycleState | None:
        """Return the CycleState for the given name, resolving aliases."""
        return self.cycles.get(name)

    def era(self, name: str) -> EraState | None:
        """Return the EraState for the given era name."""
        return self.eras.get(name)


class InGameTimeResolver:
    """Converts tick counters to InGameTimeView using a pre-analyzed GameTimeSpec.

    Constructed once at registry load time. All heavy cycle-graph computation
    (ticks_per_cycle, epoch_offset, alias resolution) is done in __init__ so
    that resolve() is pure arithmetic with no lookups.
    """

    def __init__(self, spec: "GameTimeSpec", epoch_offset: int) -> None:
        self._spec = spec
        self._epoch_offset = epoch_offset
        # Map every cycle name (and alias) to its canonical CycleSpec.
        self._by_name: Dict[str, "RootCycleSpec | DerivedCycleSpec"] = {}
        for cycle in spec.cycles:
            self._by_name[cycle.name] = cycle
            if hasattr(cycle, "aliases"):
                for alias in cycle.aliases:
                    self._by_name[alias] = cycle
        # Pre-compute ticks_per_unit for every cycle by canonical name.
        # ticks_per_unit[name] = number of root ticks in one unit of that cycle.
        self._ticks_per_unit: Dict[str, int] = {}
        for cycle in spec.cycles:
            self._ticks_per_unit[cycle.name] = self._compute_ticks_per_unit(cycle.name)

    def _compute_ticks_per_unit(self, name: str) -> int:
        """Recursively compute how many ticks make one unit of the named cycle."""
        cycle = self._by_name.get(name)
        if cycle is None:
            raise ValueError(f"Unknown cycle {name!r}")
        if cycle.type == "ticks":
            # Root cycle: 1 tick = 1 unit. count is always Literal[1].
            return 1
        # DerivedCycleSpec: one unit = count * ticks_per_unit_of_parent
        parent = self._by_name[cycle.parent]
        parent_ticks = self._compute_ticks_per_unit(parent.name)
        return cycle.count * parent_ticks

    def _cycle_label(self, cycle_name: str, effective_ticks: int) -> CycleState:
        cycle = self._by_name[cycle_name]
        canonical = cycle.name
        if cycle.type == "ticks":
            # Root cycle has count=1; position is always 0.
            ticks_per_parent = 1
        else:
            parent = self._by_name[cycle.parent]
            ticks_per_parent = self._ticks_per_unit[parent.name]
        position = (effective_ticks // ticks_per_parent) % cycle.count
        # Root cycles carry no display labels; only derived cycles have them.
        labels: List[str] = cycle.labels if cycle.type == "cycle" else []
        label = labels[position] if labels else f"{canonical} {position + 1}"
        return CycleState(name=canonical, position=position, label=label)

    def resolve(
        self,
        game_ticks: int,
        internal_ticks: int,
        player: "CharacterState",
        registry: "ContentRegistry | None",
    ) -> InGameTimeView:
        """Resolve both clocks into a full InGameTimeView."""
        effective_game = game_ticks + self._epoch_offset

        cycles: Dict[str, CycleState] = {}
        for cycle in self._spec.cycles:
            state = self._cycle_label(cycle.name, effective_game)
            cycles[cycle.name] = state
            # Also register under aliases so templates can look up either name.
            if hasattr(cycle, "aliases"):
                for alias in cycle.aliases:
                    cycles[alias] = state

        eras: Dict[str, EraState] = {}
        for era in self._spec.eras:
            # Determine activation tick. Always-active eras (no start_condition)
            # are treated as started at tick 0; conditioned eras consult the latch dict.
            if era.start_condition is None:
                started_at: int | None = 0
            else:
                started_at = player.era_started_at_ticks.get(era.name)

            ended = era.name in player.era_ended_at_ticks
            active = started_at is not None and not ended

            if started_at is not None:
                # Count: epoch_count + full tracked cycles completed since activation.
                ticks_per_tracked = self._ticks_per_unit[era.tracks]
                count = era.epoch_count + ((game_ticks - started_at) // ticks_per_tracked)
            else:
                # Era has not yet started; count defaults to epoch_count.
                count = era.epoch_count

            eras[era.name] = EraState(name=era.name, count=count, active=active)

        return InGameTimeView(
            internal_ticks=internal_ticks,
            game_ticks=game_ticks,
            cycles=cycles,
            eras=eras,
        )


def update_era_states(
    player: "CharacterState",
    spec: "GameTimeSpec",
    registry: "ContentRegistry",
) -> None:
    """Evaluate era start/end conditions and latch activation ticks into player state.

    Must be called after tick counters have been updated for the current adventure.
    Each condition fires at most once per iteration — once a condition triggers, the
    corresponding dict entry is set and the condition is never re-evaluated.
    """
    from oscilla.engine.conditions import evaluate

    for era in spec.eras:
        ended = era.name in player.era_ended_at_ticks
        if ended:
            # Era has permanently ended this iteration — never restart, even if
            # start_condition would now evaluate true. Eras happen at most once.
            continue

        started = era.start_condition is None or era.name in player.era_started_at_ticks

        if not started and era.start_condition is not None:
            if evaluate(era.start_condition, player=player, registry=registry):
                player.era_started_at_ticks[era.name] = player.game_ticks
        elif started and era.end_condition is not None:
            if evaluate(era.end_condition, player=player, registry=registry):
                player.era_ended_at_ticks[era.name] = player.game_ticks

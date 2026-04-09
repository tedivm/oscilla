"""Headless adventure path tracer.

Traces all possible execution paths through an adventure step graph.
No character state is created or modified — effects are recorded, not applied.
This is purely a static analysis tool for content authors.

Key design constraint:
    The tracer does NOT evaluate conditions (requires, bypass, stat checks).
    It treats every branch as potentially reachable and traces them all.
    A full satisfiability analysis would require a SAT solver and is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import AdventureManifest


@dataclass
class TracedEffect:
    """A recorded (but not applied) effect within a traced path."""

    effect_type: str
    summary: str  # human-readable description


@dataclass
class TracedNode:
    """One step in a traced path."""

    step_index: int
    step_type: str
    label: str | None
    description: str  # short human summary
    effects: List[TracedEffect] = field(default_factory=list)
    branch_taken: str | None = None  # e.g. "on_win", "option:Attack"


@dataclass
class TracedPath:
    """A single execution path from start to an end_adventure terminus."""

    path_id: str
    nodes: List[TracedNode] = field(default_factory=list)
    outcome: str = "(no end_adventure found)"


@dataclass
class TraceResult:
    """Full trace of all paths through an adventure."""

    adventure_name: str
    total_steps: int
    paths: List[TracedPath] = field(default_factory=list)

    @property
    def step_kinds_covered(self) -> set[str]:
        return {node.step_type for path in self.paths for node in path.nodes}

    @property
    def all_path_outcomes(self) -> list[str]:
        return [p.outcome for p in self.paths]


def trace_adventure(manifest: "AdventureManifest") -> TraceResult:
    """Trace all execution paths through an adventure.

    Each choice option, combat outcome, and stat-check branch produces a
    separate path. The resulting TraceResult contains all paths, their
    node sequences, and the recorded effects.
    """
    from oscilla.engine.graph import _walk_all_steps

    result = TraceResult(
        adventure_name=manifest.metadata.name,
        total_steps=len(_walk_all_steps(manifest.spec.steps)),
    )

    # Build a label→index map for goto resolution
    label_map: dict[str, int] = {}
    for i, step in enumerate(manifest.spec.steps):
        lbl = getattr(step, "label", None)
        if lbl:
            label_map[lbl] = i

    _trace_from_start(manifest.spec.steps, label_map, result)
    return result


def _trace_from_start(
    steps: list,
    label_map: dict[str, int],
    result: TraceResult,
) -> None:
    """Entry point: start one path and walk the top-level adventure steps."""

    def _walk(
        path: TracedPath,
        walk_steps: list,
        idx: int,
    ) -> None:
        """Walk steps sequentially, branching at choice/combat/stat_check."""
        from oscilla.engine.models.adventure import ChoiceStep, CombatStep, EndAdventureEffect, StatCheckStep

        while idx < len(walk_steps):
            step = walk_steps[idx]

            match step:
                case CombatStep():
                    _record_node(path, step, branch=None)
                    # Fork into three separate outcome paths starting from next step
                    for branch_name, branch in [
                        ("on_win", step.on_win),
                        ("on_defeat", step.on_defeat),
                        ("on_flee", step.on_flee),
                    ]:
                        fork = _fork_path(path, result)
                        # Annotate the last node of the fork with which branch was taken
                        fork.nodes[-1].branch_taken = branch_name
                        if branch.goto:
                            goto_idx = label_map.get(branch.goto, -1)
                            if goto_idx >= 0:
                                _walk(fork, walk_steps, goto_idx)
                            else:
                                fork.outcome = f"goto:{branch.goto} (unresolved)"
                                result.paths.append(fork)
                        elif branch.steps:
                            _walk(fork, branch.steps, 0)
                        else:
                            fork.outcome = branch_name
                            result.paths.append(fork)
                    return  # original path stops; forks continue

                case ChoiceStep():
                    _record_node(path, step, branch=None)
                    for opt in step.options:
                        fork = _fork_path(path, result)
                        fork.nodes[-1].branch_taken = f"option:{opt.label}"
                        _record_option_effects(fork, opt)
                        if opt.goto:
                            goto_idx = label_map.get(opt.goto, -1)
                            if goto_idx >= 0:
                                _walk(fork, walk_steps, goto_idx)
                            else:
                                fork.outcome = f"goto:{opt.goto} (unresolved)"
                                result.paths.append(fork)
                        elif opt.steps:
                            _walk(fork, opt.steps, 0)
                        else:
                            # Fall through to next top-level step after the choice
                            _walk(fork, walk_steps, idx + 1)
                    return

                case StatCheckStep():
                    _record_node(path, step, branch=None)
                    for branch_name, branch in [("on_pass", step.on_pass), ("on_fail", step.on_fail)]:
                        fork = _fork_path(path, result)
                        fork.nodes[-1].branch_taken = branch_name
                        if branch.goto:
                            goto_idx = label_map.get(branch.goto, -1)
                            if goto_idx >= 0:
                                _walk(fork, walk_steps, goto_idx)
                            else:
                                fork.outcome = f"goto:{branch.goto} (unresolved)"
                                result.paths.append(fork)
                        elif branch.steps:
                            _walk(fork, branch.steps, 0)
                        else:
                            fork.outcome = branch_name
                            result.paths.append(fork)
                    return

                case _:
                    _record_node(path, step, branch=None)
                    # Check for end_adventure in effects
                    eff_list = getattr(step, "effects", [])
                    for eff in eff_list:
                        if isinstance(eff, EndAdventureEffect):
                            path.outcome = eff.outcome
                            result.paths.append(path)
                            return

            idx += 1

        # Reached end of step list without explicit end_adventure
        path.outcome = "(no explicit end)"
        result.paths.append(path)

    initial_path = TracedPath(path_id="path-1")
    result.paths = []
    _walk(initial_path, steps, 0)


def _fork_path(parent: TracedPath, result: TraceResult) -> TracedPath:
    """Create a copy of the parent path (shallow-copy of nodes list)."""
    fork = TracedPath(
        path_id=f"path-{len(result.paths) + len([p for p in result.paths]) + 2}",
        nodes=list(parent.nodes),
    )
    return fork


def _record_node(path: TracedPath, step: object, branch: str | None) -> None:
    """Append a traced node to the path from a step object."""
    from oscilla.engine.graph import _condition_summary
    from oscilla.engine.models.adventure import ChoiceStep, CombatStep, NarrativeStep, PassiveStep, StatCheckStep

    stype = getattr(step, "type", "unknown")
    desc = ""
    effects: List[TracedEffect] = []

    match step:
        case NarrativeStep():
            text = (step.text or "")[:60].replace("\n", " ")
            desc = f"{text!r}"
            effects = _summarise_effects(step.effects)
        case CombatStep():
            desc = f"vs {step.enemy}"
        case ChoiceStep():
            desc = (step.prompt or "")[:60]
        case StatCheckStep():
            desc = _condition_summary(step.condition)
        case PassiveStep():
            desc = f"{len(step.effects)} effects"
            effects = _summarise_effects(step.effects)

    path.nodes.append(
        TracedNode(
            step_index=len(path.nodes),
            step_type=stype,
            label=getattr(step, "label", None),
            description=desc,
            effects=effects,
            branch_taken=branch,
        )
    )


def _record_option_effects(path: TracedPath, opt: object) -> None:
    """Record effects from a choice option into the last node."""
    if path.nodes and hasattr(opt, "effects"):
        path.nodes[-1].effects.extend(_summarise_effects(getattr(opt, "effects", [])))


def _summarise_effects(effects: list) -> List[TracedEffect]:
    from oscilla.engine.models.adventure import (
        EndAdventureEffect,
        HealEffect,
        ItemDropEffect,
        MilestoneGrantEffect,
        SkillGrantEffect,
        StatChangeEffect,
        StatSetEffect,
    )

    result = []
    for eff in effects:
        match eff:
            case HealEffect(amount=a):
                result.append(TracedEffect("heal", f"heal {a}"))
            case StatChangeEffect(stat=s, amount=a):
                result.append(TracedEffect("stat_change", f"{s} +{a}"))
            case StatSetEffect(stat=s, value=v):
                result.append(TracedEffect("stat_set", f"{s} = {v}"))
            case MilestoneGrantEffect(milestone=m):
                result.append(TracedEffect("milestone_grant", f"milestone: {m}"))
            case SkillGrantEffect(skill=sk):
                result.append(TracedEffect("skill_grant", f"skill: {sk}"))
            case ItemDropEffect():
                if eff.loot_ref:
                    result.append(TracedEffect("item_drop", f"drop from loot_table: {eff.loot_ref}"))
                elif eff.loot:
                    for entry in eff.loot:
                        result.append(TracedEffect("item_drop", f"drop: {entry.item}"))
            case EndAdventureEffect(outcome=o):
                result.append(TracedEffect("end_adventure", f"outcome: {o}"))
    return result

"""Semantic validation of a fully loaded ContentRegistry.

These checks are deliberately post-load: they require a complete, schema-valid
registry to operate against. They catch errors that Pydantic schema validation
cannot — broken cross-manifest references, circular structures, and
unreachable content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Set, Tuple

if TYPE_CHECKING:
    from oscilla.engine.registry import ContentRegistry


@dataclass
class SemanticIssue:
    kind: str  # "undefined_ref", "circular_chain", "orphaned", "unreachable"
    message: str
    manifest: str | None = None
    severity: str = "error"  # "error" | "warning"

    def __str__(self) -> str:
        prefix = f"[{self.manifest}] " if self.manifest else ""
        return f"{prefix}{self.message}"


def validate_semantic(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Run all semantic checks. Returns a list of issues (errors and warnings).

    Callers decide whether to treat warnings as errors (strict mode).
    """
    issues: List[SemanticIssue] = []
    issues.extend(_check_undefined_adventure_refs(registry))
    issues.extend(_check_undefined_enemy_refs(registry))
    issues.extend(_check_undefined_item_refs(registry))
    issues.extend(_check_undefined_skill_refs(registry))
    issues.extend(_check_circular_region_parents(registry))
    issues.extend(_check_orphaned_adventures(registry))
    issues.extend(_check_unreachable_adventures(registry))
    issues.extend(_validate_time_spec(registry))
    issues.extend(_check_missing_descriptions(registry))
    return issues


def _check_undefined_adventure_refs(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Location adventure pools may reference adventure names that don't exist."""
    issues = []
    for loc in registry.locations.all():
        for entry in loc.spec.adventures:
            if registry.adventures.get(entry.ref) is None:
                issues.append(
                    SemanticIssue(
                        kind="undefined_ref",
                        message=f"Adventure pool references unknown adventure {entry.ref!r}",
                        manifest=f"location:{loc.metadata.name}",
                    )
                )
    return issues


def _check_undefined_enemy_refs(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Combat steps reference enemy manifest names."""
    from oscilla.engine.graph import _walk_all_steps
    from oscilla.engine.models.adventure import CombatStep

    issues = []
    for adv in registry.adventures.all():
        for step in _walk_all_steps(adv.spec.steps):
            if isinstance(step, CombatStep):
                if registry.enemies.get(step.enemy) is None:
                    issues.append(
                        SemanticIssue(
                            kind="undefined_ref",
                            message=f"Combat step references unknown enemy {step.enemy!r}",
                            manifest=f"adventure:{adv.metadata.name}",
                        )
                    )
    return issues


def _check_undefined_item_refs(registry: "ContentRegistry") -> List[SemanticIssue]:
    """ItemDropEffects and LootTable entries reference item manifest names."""
    from oscilla.engine.graph import _walk_all_effects
    from oscilla.engine.models.adventure import ItemDropEffect

    issues = []
    for adv in registry.adventures.all():
        for effect in _walk_all_effects(adv.spec.steps):
            if isinstance(effect, ItemDropEffect) and effect.groups:
                for group in effect.groups:
                    for entry in group.entries:
                        if registry.items.get(entry.item) is None:
                            issues.append(
                                SemanticIssue(
                                    kind="undefined_ref",
                                    message=f"item_drop references unknown item {entry.item!r}",
                                    manifest=f"adventure:{adv.metadata.name}",
                                )
                            )

    for lt in registry.loot_tables.all():
        for group in lt.spec.groups:
            for entry in group.entries:
                if registry.items.get(entry.item) is None:
                    issues.append(
                        SemanticIssue(
                            kind="undefined_ref",
                            message=f"LootTable entry references unknown item {entry.item!r}",
                            manifest=f"loot-table:{lt.metadata.name}",
                        )
                    )
    return issues


def _check_undefined_skill_refs(registry: "ContentRegistry") -> List[SemanticIssue]:
    """SkillGrantEffects reference skill manifest names."""
    from oscilla.engine.graph import _walk_all_effects
    from oscilla.engine.models.adventure import SkillGrantEffect

    issues = []
    for adv in registry.adventures.all():
        for effect in _walk_all_effects(adv.spec.steps):
            if isinstance(effect, SkillGrantEffect):
                if registry.skills.get(effect.skill) is None:
                    issues.append(
                        SemanticIssue(
                            kind="undefined_ref",
                            message=f"skill_grant references unknown skill {effect.skill!r}",
                            manifest=f"adventure:{adv.metadata.name}",
                        )
                    )
    return issues


def _check_circular_region_parents(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Region parent chains must be acyclic.

    Uses a depth-first search with a visited/recursion-stack approach.
    """
    issues: List[SemanticIssue] = []
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def _dfs(name: str) -> bool:
        visited.add(name)
        rec_stack.add(name)
        region = registry.regions.get(name)
        if region and region.spec.parent:
            parent = region.spec.parent
            if parent not in visited:
                if _dfs(parent):
                    return True
            elif parent in rec_stack:
                issues.append(
                    SemanticIssue(
                        kind="circular_chain",
                        message=f"Circular region parent chain detected at {name!r} → {parent!r}",
                        manifest=f"region:{name}",
                    )
                )
                return True
        rec_stack.discard(name)
        return False

    for region in registry.regions.all():
        if region.metadata.name not in visited:
            _dfs(region.metadata.name)

    return issues


def _check_orphaned_adventures(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Adventures that are defined but not referenced in any location's pool are orphaned.

    Orphaned adventures are surfaced as warnings — the author may be drafting
    them — but they never run and can't be reached by players.

    Adventures wired to triggers via trigger_adventures are not orphaned — they
    run automatically when the trigger fires and do not need a location pool entry.
    """
    referenced: Set[str] = set()
    for loc in registry.locations.all():
        for entry in loc.spec.adventures:
            referenced.add(entry.ref)

    # Adventures referenced by any trigger are reachable; exclude them from the orphan check.
    if registry.game is not None:
        for adv_refs in registry.game.spec.trigger_adventures.values():
            referenced.update(adv_refs)

    issues = []
    for adv in registry.adventures.all():
        if adv.metadata.name not in referenced:
            issues.append(
                SemanticIssue(
                    kind="orphaned",
                    message=f"Adventure {adv.metadata.name!r} is not referenced in any location's pool",
                    manifest=f"adventure:{adv.metadata.name}",
                    severity="warning",
                )
            )
    return issues


def _check_unreachable_adventures(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Report adventures in location pools whose requires condition references an unknown milestone.

    A complete reachability analysis (satisfiability of conditions) is out of
    scope. This check only flags adventures whose conditions reference milestone
    names that are never granted anywhere in any adventure.
    """
    from oscilla.engine.graph import _walk_all_effects
    from oscilla.engine.models.adventure import MilestoneGrantEffect
    from oscilla.engine.models.base import MilestoneCondition

    # Collect all milestones that are ever granted.
    grantable_milestones: Set[str] = set()
    for adv in registry.adventures.all():
        for effect in _walk_all_effects(adv.spec.steps):
            if isinstance(effect, MilestoneGrantEffect):
                grantable_milestones.add(effect.milestone)

    issues = []
    for loc in registry.locations.all():
        for entry in loc.spec.adventures:
            if entry.requires is not None and isinstance(entry.requires, MilestoneCondition):
                ms = entry.requires.name
                if ms not in grantable_milestones:
                    issues.append(
                        SemanticIssue(
                            kind="unreachable",
                            message=(
                                f"Adventure pool entry {entry.ref!r} requires milestone {ms!r} "
                                f"which is never granted by any adventure"
                            ),
                            manifest=f"location:{loc.metadata.name}",
                            severity="warning",
                        )
                    )
    return issues


def _validate_time_spec(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Validate the game time spec (game.yaml spec.time) for structural correctness.

    Checks:
    1. Exactly one root cycle (type: ticks).
    2. No circular parent references in the cycle DAG.
    3. All parent names resolve to a declared cycle name or alias.
    4. No duplicate names or aliases across all cycles.
    5. Labels list length matches count when labels are supplied.
    6. Epoch keys are declared cycle names/aliases; values are valid labels or in-range integers.
    7. Era `tracks` references a declared cycle.
    8. `game_calendar_cycle_is` conditions reference declared cycles; values match declared labels.
    9. `game_calendar_era_is` conditions reference declared eras.
    """
    if registry.game is None or registry.game.spec.time is None:
        return []

    from oscilla.engine.models.base import (
        AllCondition,
        AnyCondition,
        GameCalendarCycleCondition,
        GameCalendarEraCondition,
        NotCondition,
    )
    from oscilla.engine.models.time import DerivedCycleSpec, RootCycleSpec

    issues: List[SemanticIssue] = []
    spec = registry.game.spec.time

    # --- Build lookup maps ---
    # Map every name/alias → canonical cycle name
    name_to_canonical: Dict[str, str] = {}
    # Map canonical name → cycle spec
    canonical_to_spec: Dict[str, RootCycleSpec | DerivedCycleSpec] = {}
    duplicate_names: Set[str] = set()

    for cycle in spec.cycles:
        tokens = [cycle.name]
        if isinstance(cycle, RootCycleSpec):
            tokens.extend(cycle.aliases)
        for token in tokens:
            if token in name_to_canonical:
                duplicate_names.add(token)
            else:
                name_to_canonical[token] = cycle.name
        canonical_to_spec[cycle.name] = cycle

    era_names: Set[str] = {era.name for era in spec.eras}

    # Rule 4: Duplicate names/aliases
    for dup in sorted(duplicate_names):
        issues.append(
            SemanticIssue(
                kind="duplicate_name",
                message=f"Duplicate cycle name or alias {dup!r} in time spec",
                manifest="game",
            )
        )

    # Rule 1: Exactly one root cycle
    root_cycles = [c for c in spec.cycles if isinstance(c, RootCycleSpec)]
    if len(root_cycles) == 0:
        issues.append(
            SemanticIssue(
                kind="invalid_time_spec",
                message="time.cycles must contain exactly one root cycle (type: ticks); found none",
                manifest="game",
            )
        )
    elif len(root_cycles) > 1:
        names = ", ".join(repr(c.name) for c in root_cycles)
        issues.append(
            SemanticIssue(
                kind="invalid_time_spec",
                message=f"time.cycles must contain exactly one root cycle (type: ticks); found {len(root_cycles)}: {names}",
                manifest="game",
            )
        )

    # Rule 3: All parent names resolve + Rule 2: No circular parent refs
    for cycle in spec.cycles:
        if isinstance(cycle, DerivedCycleSpec):
            if cycle.parent not in name_to_canonical:
                issues.append(
                    SemanticIssue(
                        kind="undefined_ref",
                        message=f"Cycle {cycle.name!r} parent {cycle.parent!r} does not resolve to any declared cycle",
                        manifest="game",
                    )
                )

    # Rule 2: Circular parent refs (DFS)
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def _dfs_cycle(name: str) -> bool:
        visited.add(name)
        rec_stack.add(name)
        cyc = canonical_to_spec.get(name)
        if cyc is not None and isinstance(cyc, DerivedCycleSpec):
            parent_canonical = name_to_canonical.get(cyc.parent)
            if parent_canonical is not None:
                if parent_canonical not in visited:
                    if _dfs_cycle(parent_canonical):
                        return True
                elif parent_canonical in rec_stack:
                    issues.append(
                        SemanticIssue(
                            kind="circular_chain",
                            message=f"Circular parent chain detected in cycles: {name!r} → {cyc.parent!r}",
                            manifest="game",
                        )
                    )
                    return True
        rec_stack.discard(name)
        return False

    for cycle in spec.cycles:
        if cycle.name not in visited:
            _dfs_cycle(cycle.name)

    # Rule 5: Labels length = count — only applicable to derived cycles (root has no labels)
    for cycle in spec.cycles:
        if cycle.type == "cycle" and cycle.labels and len(cycle.labels) != cycle.count:
            issues.append(
                SemanticIssue(
                    kind="invalid_time_spec",
                    message=(
                        f"Cycle {cycle.name!r} has {len(cycle.labels)} labels but count={cycle.count}; they must match"
                    ),
                    manifest="game",
                )
            )

    # Rule 6: Epoch keys and values
    for key, value in spec.epoch.items():
        canonical = name_to_canonical.get(key)
        if canonical is None:
            issues.append(
                SemanticIssue(
                    kind="undefined_ref",
                    message=f"Epoch key {key!r} does not resolve to any declared cycle",
                    manifest="game",
                )
            )
            continue
        cycle = canonical_to_spec[canonical]
        if isinstance(value, str):
            labels = cycle.labels if cycle.type == "cycle" else []
            if labels and value not in labels:
                issues.append(
                    SemanticIssue(
                        kind="invalid_time_spec",
                        message=(f"Epoch value {value!r} for cycle {key!r} is not in declared labels: {labels!r}"),
                        manifest="game",
                    )
                )
        else:
            # 1-based integer
            if value < 1 or value > cycle.count:
                issues.append(
                    SemanticIssue(
                        kind="invalid_time_spec",
                        message=(f"Epoch value {value!r} for cycle {key!r} is out of range; must be 1..{cycle.count}"),
                        manifest="game",
                    )
                )

    # Rule 7: Era `tracks` references declared cycles
    for era in spec.eras:
        if era.tracks not in name_to_canonical:
            issues.append(
                SemanticIssue(
                    kind="undefined_ref",
                    message=f"Era {era.name!r} tracks cycle {era.tracks!r} which is not declared",
                    manifest="game",
                )
            )

    # Rules 8 + 9: Walk all conditions in the registry and validate calendar refs
    def _collect_calendar_conditions(condition: object) -> List[object]:
        """Recursively collect all calendar conditions from a condition tree."""
        if condition is None:
            return []
        result: List[object] = []
        if isinstance(condition, (GameCalendarCycleCondition, GameCalendarEraCondition)):
            result.append(condition)
        elif isinstance(condition, (AllCondition, AnyCondition)):
            for sub in condition.conditions:
                result.extend(_collect_calendar_conditions(sub))
        elif isinstance(condition, NotCondition):
            result.extend(_collect_calendar_conditions(condition.condition))
        return result

    def _check_calendar_conditions(conditions: List[object], source: str) -> None:
        for cond in conditions:
            if isinstance(cond, GameCalendarCycleCondition):
                canonical = name_to_canonical.get(cond.cycle)
                if canonical is None:
                    issues.append(
                        SemanticIssue(
                            kind="undefined_ref",
                            message=f"game_calendar_cycle_is references unknown cycle {cond.cycle!r}",
                            manifest=source,
                        )
                    )
                else:
                    cycle = canonical_to_spec[canonical]
                    labels = cycle.labels if cycle.type == "cycle" else []
                    if labels and cond.value not in labels:
                        issues.append(
                            SemanticIssue(
                                kind="invalid_time_spec",
                                message=(
                                    f"game_calendar_cycle_is value {cond.value!r} for cycle {cond.cycle!r} "
                                    f"is not in declared labels: {labels!r}"
                                ),
                                manifest=source,
                            )
                        )
            elif isinstance(cond, GameCalendarEraCondition):
                if cond.era not in era_names:
                    issues.append(
                        SemanticIssue(
                            kind="undefined_ref",
                            message=f"game_calendar_era_is references unknown era {cond.era!r}",
                            manifest=source,
                        )
                    )

    # Check era start/end conditions
    for era in spec.eras:
        for cond_field in (era.start_condition, era.end_condition):
            cal_conds = _collect_calendar_conditions(cond_field)
            _check_calendar_conditions(cal_conds, source=f"era:{era.name}")

    # Check all conditions in adventures (requires + step conditions)
    from oscilla.engine.graph import _walk_all_steps
    from oscilla.engine.models.adventure import ChoiceStep, StatCheckStep

    for adv in registry.adventures.all():
        src = f"adventure:{adv.metadata.name}"
        cal_conds = _collect_calendar_conditions(adv.spec.requires)
        _check_calendar_conditions(cal_conds, source=src)
        for step in _walk_all_steps(adv.spec.steps):
            if isinstance(step, StatCheckStep):
                cal_conds = _collect_calendar_conditions(step.condition)
                _check_calendar_conditions(cal_conds, source=src)
            elif isinstance(step, ChoiceStep):
                for opt in step.options:
                    cal_conds = _collect_calendar_conditions(opt.requires)
                    _check_calendar_conditions(cal_conds, source=src)

    # Check location adventure pool conditions
    for loc in registry.locations.all():
        src = f"location:{loc.metadata.name}"
        for entry in loc.spec.adventures:
            cal_conds = _collect_calendar_conditions(entry.requires)
            _check_calendar_conditions(cal_conds, source=src)

    return issues


# API-exposed manifest kinds whose description field is player-visible.
# displayName has no default and is already enforced by Pydantic — only description needs a warning.
_DESCRIPTION_CHECKS: List[Tuple[str, str]] = [
    ("adventure", "adventures"),
    ("item", "items"),
    ("skill", "skills"),
    ("buff", "buffs"),
    ("quest", "quests"),
    ("archetype", "archetypes"),
    ("location", "locations"),
    ("region", "regions"),
]


def _check_missing_descriptions(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Warn when an API-exposed manifest kind has no description set.

    An empty description means the API returns null for that field and the
    frontend silently omits it. This is usually an authoring oversight because
    description defaults to an empty string.
    """
    issues: List[SemanticIssue] = []
    for kind_label, registry_attr in _DESCRIPTION_CHECKS:
        kind_registry = getattr(registry, registry_attr)
        for manifest in kind_registry.all():
            if not manifest.spec.description:
                issues.append(
                    SemanticIssue(
                        kind="missing_description",
                        message=f"{kind_label} {manifest.metadata.name!r} has no description",
                        manifest=f"{kind_label}:{manifest.metadata.name}",
                        severity="warning",
                    )
                )
    return issues

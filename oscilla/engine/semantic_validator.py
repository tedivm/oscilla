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
    from oscilla.engine.models.base import Condition
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
    issues.extend(_check_heal_enemy_deprecation(registry))
    issues.extend(_check_combat_system_required(registry))
    issues.extend(_check_player_turn_mode_conflict(registry))
    issues.extend(_check_initiative_formula_requirements(registry))
    issues.extend(_check_enemy_stat_coverage(registry))
    issues.extend(_check_combat_stat_condition_refs(registry))
    issues.extend(_check_system_skill_refs(registry))
    issues.extend(_check_target_stat_null_validity(registry))
    issues.extend(_check_formula_mock_render(registry))
    issues.extend(_check_dynamic_stat_change_value(registry))
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


def _check_heal_enemy_deprecation(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Warn when any adventure step uses ``heal target='enemy'``.

    Direct enemy healing via the HealEffect is deprecated. Authors should
    instead use ``stat_change target='enemy'`` with a positive amount on the
    appropriate enemy stat (typically ``hp``).
    """
    from oscilla.engine.graph import _walk_all_effects
    from oscilla.engine.models.adventure import HealEffect

    issues: List[SemanticIssue] = []
    for adv in registry.adventures.all():
        for effect in _walk_all_effects(adv.spec.steps):
            if isinstance(effect, HealEffect) and effect.target == "enemy":
                issues.append(
                    SemanticIssue(
                        kind="deprecated_heal_enemy",
                        message=(
                            "heal with target='enemy' is deprecated; use "
                            "stat_change target='enemy' with a positive amount instead."
                        ),
                        manifest=f"Adventure:{adv.metadata.name}",
                        severity="warning",
                    )
                )
    return issues


def _check_combat_system_required(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Error if any adventure contains a CombatStep but no CombatSystem is resolvable."""
    from oscilla.engine.graph import _walk_all_steps
    from oscilla.engine.models.adventure import CombatStep

    issues: List[SemanticIssue] = []
    for adv in registry.adventures.all():
        for step in _walk_all_steps(adv.spec.steps):
            if isinstance(step, CombatStep):
                resolved = registry.resolve_combat_system(step.combat_system)
                if resolved is None:
                    issues.append(
                        SemanticIssue(
                            kind="no_combat_system",
                            message=(
                                f"Combat step targeting enemy {step.enemy!r} has no resolvable "
                                "CombatSystem. Define default_combat_system in game.yaml or "
                                "register exactly one CombatSystem manifest."
                            ),
                            manifest=f"adventure:{adv.metadata.name}",
                        )
                    )
    return issues


def _check_player_turn_mode_conflict(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Error if a CombatSystem uses choice mode but also defines player_damage_formulas."""
    issues: List[SemanticIssue] = []
    for cs in registry.combat_systems.all():
        if cs.spec.player_turn_mode == "choice" and cs.spec.player_damage_formulas:
            issues.append(
                SemanticIssue(
                    kind="choice_mode_with_damage_formulas",
                    message=(
                        "player_turn_mode is 'choice' but player_damage_formulas is non-empty. "
                        "In choice mode, player_damage_formulas are ignored — move them to skill "
                        "manifests or remove them."
                    ),
                    manifest=f"CombatSystem:{cs.metadata.name}",
                )
            )
    return issues


def _check_initiative_formula_requirements(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Error if initiative mode is missing formulas; warn if formulas present without initiative."""
    issues: List[SemanticIssue] = []
    for cs in registry.combat_systems.all():
        spec = cs.spec
        name = f"CombatSystem:{cs.metadata.name}"
        if spec.turn_order == "initiative":
            if spec.player_initiative_formula is None:
                issues.append(
                    SemanticIssue(
                        kind="initiative_formula_missing",
                        message="turn_order is 'initiative' but player_initiative_formula is not set.",
                        manifest=name,
                    )
                )
            if spec.enemy_initiative_formula is None:
                issues.append(
                    SemanticIssue(
                        kind="initiative_formula_missing",
                        message="turn_order is 'initiative' but enemy_initiative_formula is not set.",
                        manifest=name,
                    )
                )
        else:
            if spec.player_initiative_formula is not None or spec.enemy_initiative_formula is not None:
                issues.append(
                    SemanticIssue(
                        kind="initiative_formula_unused",
                        message=(
                            "Initiative formulas are defined but turn_order is not 'initiative' — "
                            "the formulas will never be used."
                        ),
                        manifest=name,
                        severity="warning",
                    )
                )
    return issues


def _check_enemy_stat_coverage(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Error when an enemy is missing a stat key required by the applicable CombatSystem."""
    from oscilla.engine.graph import _walk_all_steps
    from oscilla.engine.models.adventure import CombatStep

    issues: List[SemanticIssue] = []
    # Track (enemy_name, combat_system_name) pairs already checked to avoid duplicates.
    checked: Set[Tuple[str, str]] = set()
    for adv in registry.adventures.all():
        for step in _walk_all_steps(adv.spec.steps):
            if not isinstance(step, CombatStep):
                continue
            cs = registry.resolve_combat_system(step.combat_system)
            if cs is None:
                continue  # already caught by _check_combat_system_required
            enemy = registry.enemies.get(step.enemy)
            if enemy is None:
                continue  # already caught by _check_undefined_enemy_refs
            key = (step.enemy, cs.metadata.name)
            if key in checked:
                continue
            checked.add(key)
            required_stats = {
                e.target_stat
                for e in cs.spec.player_damage_formulas + cs.spec.enemy_damage_formulas
                if e.target_stat is not None and (e.target is None or e.target == "enemy")
            }
            missing = required_stats - set(enemy.spec.stats.keys())
            for stat in sorted(missing):
                issues.append(
                    SemanticIssue(
                        kind="enemy_stat_missing",
                        message=(
                            f"Enemy {step.enemy!r} is missing stat {stat!r} required by "
                            f"CombatSystem {cs.metadata.name!r}."
                        ),
                        manifest=f"Enemy:{step.enemy}",
                    )
                )
    return issues


def _walk_condition_tree(condition: "Condition") -> "List[Condition]":
    """Flatten a nested condition tree into a list including the root and all descendants."""
    from oscilla.engine.models.base import AllCondition, AnyCondition, NotCondition

    result: List = [condition]
    if isinstance(condition, (AllCondition, AnyCondition)):
        for sub in condition.conditions:
            result.extend(_walk_condition_tree(sub))
    elif isinstance(condition, NotCondition):
        result.extend(_walk_condition_tree(condition.condition))
    return result


def _check_combat_stat_condition_refs(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Verify stat references in defeat conditions match declared combat_stats entries."""
    from oscilla.engine.models.base import CombatStatCondition, EnemyStatCondition

    issues: List[SemanticIssue] = []
    for cs in registry.combat_systems.all():
        name = f"CombatSystem:{cs.metadata.name}"
        declared_combat_stats = {e.name for e in cs.spec.combat_stats}
        for cond_field, cond in [
            ("player_defeat_condition", cs.spec.player_defeat_condition),
            ("enemy_defeat_condition", cs.spec.enemy_defeat_condition),
        ]:
            for leaf in _walk_condition_tree(cond):
                if isinstance(leaf, CombatStatCondition):
                    if leaf.stat not in declared_combat_stats:
                        issues.append(
                            SemanticIssue(
                                kind="undeclared_combat_stat",
                                message=(
                                    f"{cond_field} references combat stat {leaf.stat!r} which is "
                                    "not declared in the combat_stats list."
                                ),
                                manifest=name,
                            )
                        )
                elif isinstance(leaf, EnemyStatCondition):
                    # EnemyStatCondition keys are dynamic (per enemy manifest) — warn only.
                    issues.append(
                        SemanticIssue(
                            kind="enemy_stat_condition_unverifiable",
                            message=(
                                f"{cond_field} uses enemy_stat condition on {leaf.stat!r}. "
                                "Verify this stat is populated in all relevant enemy manifests."
                            ),
                            manifest=name,
                            severity="warning",
                        )
                    )
    return issues


def _check_system_skill_refs(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Error when a SystemSkillEntry references a skill not present in the registry."""
    issues: List[SemanticIssue] = []
    for cs in registry.combat_systems.all():
        for entry in cs.spec.system_skills:
            if registry.skills.get(entry.skill) is None:
                issues.append(
                    SemanticIssue(
                        kind="undefined_ref",
                        message=f"system_skills references unknown skill {entry.skill!r}",
                        manifest=f"CombatSystem:{cs.metadata.name}",
                    )
                )
    return issues


def _check_target_stat_null_validity(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Error if a DamageFormulaEntry has target_stat=None and empty threshold_effects.

    Such an entry has no effect and is almost certainly a content authoring mistake.
    """
    issues: List[SemanticIssue] = []
    for cs in registry.combat_systems.all():
        name = f"CombatSystem:{cs.metadata.name}"
        spec = cs.spec
        all_entries = spec.player_damage_formulas + spec.enemy_damage_formulas + spec.resolution_formulas
        for entry in all_entries:
            if entry.target_stat is None and not entry.threshold_effects:
                issues.append(
                    SemanticIssue(
                        kind="no_op_formula",
                        message=(
                            f"DamageFormulaEntry has target_stat=null and no threshold_effects "
                            f"— the formula {entry.formula!r} will have no effect"
                        ),
                        manifest=name,
                    )
                )
    return issues


def _check_formula_mock_render(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Error if any CombatSystem formula fails Jinja2 syntax validation at load time."""
    from oscilla.engine.templates import CombatFormulaContext, FormulaRenderError, render_formula

    issues: List[SemanticIssue] = []
    zero_ctx = CombatFormulaContext(
        player={},
        enemy_stats={},
        combat_stats={},
        turn_number=0,
    )
    for cs in registry.combat_systems.all():
        name = f"CombatSystem:{cs.metadata.name}"
        spec = cs.spec
        formula_entries: List[Tuple[str, str]] = []
        for entry in spec.player_damage_formulas + spec.enemy_damage_formulas + spec.resolution_formulas:
            label = f"formula targeting {entry.target_stat or '(threshold-only)'}"
            formula_entries.append((label, entry.formula))
        if spec.player_initiative_formula:
            formula_entries.append(("player_initiative_formula", spec.player_initiative_formula))
        if spec.enemy_initiative_formula:
            formula_entries.append(("enemy_initiative_formula", spec.enemy_initiative_formula))
        for label, formula in formula_entries:
            try:
                render_formula(formula=formula, ctx=zero_ctx)
            except FormulaRenderError as exc:
                issues.append(
                    SemanticIssue(
                        kind="formula_render_error",
                        message=f"{label}: formula failed to render — {exc}",
                        manifest=name,
                    )
                )
            except Exception as exc:
                issues.append(
                    SemanticIssue(
                        kind="formula_render_error",
                        message=f"{label}: unexpected error during formula render — {exc}",
                        manifest=name,
                    )
                )
    return issues


def _check_dynamic_stat_change_value(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Validate string amounts in stat_change effects inside threshold_effects bands.

    String amounts in threshold_effects are rendered via render_formula — these are
    validated by mock-rendering with a zeroed CombatFormulaContext.

    String amounts in CombatSystem lifecycle hooks (on_combat_start, on_round_end, etc.)
    are not supported and produce a hard error.
    """
    from oscilla.engine.models.adventure import StatChangeEffect
    from oscilla.engine.templates import CombatFormulaContext, FormulaRenderError, render_formula

    issues: List[SemanticIssue] = []
    zero_ctx = CombatFormulaContext(
        player={},
        enemy_stats={},
        combat_stats={},
        turn_number=0,
    )
    for cs in registry.combat_systems.all():
        name = f"CombatSystem:{cs.metadata.name}"
        spec = cs.spec

        # Validate formula-style amounts in threshold_effects bands.
        for entry in spec.player_damage_formulas + spec.enemy_damage_formulas + spec.resolution_formulas:
            for band in entry.threshold_effects:
                for effect in band.effects:
                    if isinstance(effect, StatChangeEffect) and isinstance(effect.amount, str):
                        try:
                            render_formula(formula=effect.amount, ctx=zero_ctx)
                        except (FormulaRenderError, Exception) as exc:
                            issues.append(
                                SemanticIssue(
                                    kind="dynamic_stat_change_invalid",
                                    message=(
                                        f"threshold_effects stat_change has invalid formula "
                                        f"amount {effect.amount!r}: {exc}"
                                    ),
                                    manifest=name,
                                )
                            )

        # String amounts in lifecycle hooks are not yet supported — emit hard error.
        lifecycle_hooks: List[Tuple[str, List]] = [
            ("on_combat_start", spec.on_combat_start),
            ("on_combat_end", spec.on_combat_end),
            ("on_combat_victory", spec.on_combat_victory),
            ("on_combat_defeat", spec.on_combat_defeat),
            ("on_round_end", spec.on_round_end),
        ]
        for hook_name, hook_effects in lifecycle_hooks:
            for effect in hook_effects:
                if isinstance(effect, StatChangeEffect) and isinstance(effect.amount, str):
                    issues.append(
                        SemanticIssue(
                            kind="dynamic_stat_change_unsupported",
                            message=(
                                f"{hook_name} stat_change has string amount {effect.amount!r} — "
                                "dynamic amounts in CombatSystem lifecycle hooks are not supported. "
                                "Use an integer amount instead."
                            ),
                            manifest=name,
                        )
                    )
    return issues

"""Semantic validation of a fully loaded ContentRegistry.

These checks are deliberately post-load: they require a complete, schema-valid
registry to operate against. They catch errors that Pydantic schema validation
cannot — broken cross-manifest references, circular structures, and
unreachable content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Set

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
            if isinstance(effect, ItemDropEffect) and effect.loot:
                for entry in effect.loot:
                    if registry.items.get(entry.item) is None:
                        issues.append(
                            SemanticIssue(
                                kind="undefined_ref",
                                message=f"item_drop references unknown item {entry.item!r}",
                                manifest=f"adventure:{adv.metadata.name}",
                            )
                        )

    for lt in registry.loot_tables.all():
        for entry in lt.spec.loot:
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
    """
    referenced: Set[str] = set()
    for loc in registry.locations.all():
        for entry in loc.spec.adventures:
            referenced.add(entry.ref)

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

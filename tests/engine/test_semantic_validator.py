"""Tests for semantic_validator.py."""

from __future__ import annotations


from oscilla.engine.models.adventure import (
    AdventureManifest,
    AdventureSpec,
    CombatStep,
    EndAdventureEffect,
    NarrativeStep,
    OutcomeBranch,
)
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.location import LocationManifest, LocationSpec
from oscilla.engine.models.region import RegionManifest, RegionSpec
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.semantic_validator import SemanticIssue, validate_semantic


def _base_region(name: str = "forest") -> RegionManifest:
    return RegionManifest(
        apiVersion="game/v1",
        kind="Region",
        metadata=Metadata(name=name),
        spec=RegionSpec(displayName=name.title()),
    )


def _base_location(name: str = "clearing", region: str = "forest") -> LocationManifest:
    return LocationManifest(
        apiVersion="game/v1",
        kind="Location",
        metadata=Metadata(name=name),
        spec=LocationSpec(displayName=name.title(), region=region),
    )


def _base_adventure(name: str = "find-sword") -> AdventureManifest:
    return AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=Metadata(name=name),
        spec=AdventureSpec(
            displayName=name.title(),
            steps=[
                NarrativeStep(type="narrative", text="You find a sword."),
                NarrativeStep(
                    type="narrative",
                    text="Done.",
                    effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                ),
            ],
        ),
    )


def test_no_issues_on_clean_registry() -> None:
    """A well-formed registry with no cross-ref problems should produce no issues."""
    from oscilla.engine.models.location import AdventurePoolEntry

    region = _base_region()
    adventure = _base_adventure()
    location = LocationManifest(
        apiVersion="game/v1",
        kind="Location",
        metadata=Metadata(name="clearing"),
        spec=LocationSpec(
            displayName="Clearing",
            region="forest",
            adventures=[AdventurePoolEntry(ref="find-sword", weight=1)],
        ),
    )
    registry = ContentRegistry.build(manifests=[region, location, adventure])
    issues = validate_semantic(registry)
    # Only warnings are acceptable (e.g. unreachable adventures), but no errors.
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []


def test_undefined_adventure_ref_in_pool() -> None:
    """Location adventure pool references a non-existent adventure."""
    from oscilla.engine.models.location import AdventurePoolEntry

    region = _base_region()
    location = LocationManifest(
        apiVersion="game/v1",
        kind="Location",
        metadata=Metadata(name="clearing"),
        spec=LocationSpec(
            displayName="Clearing",
            region="forest",
            adventures=[AdventurePoolEntry(ref="ghost-town", weight=1)],
        ),
    )
    registry = ContentRegistry.build(manifests=[region, location])
    issues = validate_semantic(registry)
    errors = [i for i in issues if i.severity == "error"]
    assert any("ghost-town" in i.message for i in errors)


def test_circular_region_parents() -> None:
    """Two regions that are each other's parent create a cycle."""
    region_a = RegionManifest(
        apiVersion="game/v1",
        kind="Region",
        metadata=Metadata(name="forest"),
        spec=RegionSpec(displayName="Forest", parent="mountains"),
    )
    region_b = RegionManifest(
        apiVersion="game/v1",
        kind="Region",
        metadata=Metadata(name="mountains"),
        spec=RegionSpec(displayName="Mountains", parent="forest"),
    )
    registry = ContentRegistry.build(manifests=[region_a, region_b])
    issues = validate_semantic(registry)
    errors = [i for i in issues if i.severity == "error"]
    assert any("circular" in i.message.lower() or "cycle" in i.message.lower() for i in errors)


def test_orphaned_adventure_is_warning() -> None:
    """An adventure not in any location pool should generate a warning, not an error."""
    region = _base_region()
    location = _base_location()  # no adventure pool entries
    adventure = _base_adventure("orphan-quest")
    registry = ContentRegistry.build(manifests=[region, location, adventure])
    issues = validate_semantic(registry)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("orphan" in i.kind or "orphan-quest" in i.message for i in warnings)


def test_semantic_issue_str_includes_manifest_name() -> None:
    issue = SemanticIssue(
        kind="undefined_ref",
        message="Adventure pool references unknown adventure 'foo'",
        manifest="location:clearing",
    )
    result = str(issue)
    assert "location:clearing" in result
    assert "foo" in result


def test_semantic_issue_str_without_manifest() -> None:
    issue = SemanticIssue(
        kind="circular_chain",
        message="Circular region parents detected",
    )
    result = str(issue)
    assert "Circular" in result


def test_undefined_enemy_in_combat_step() -> None:
    """A combat step referencing an unknown enemy should produce an error."""
    region = _base_region()
    location = _base_location()
    adventure = AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=Metadata(name="fight"),
        spec=AdventureSpec(
            displayName="Fight",
            steps=[
                CombatStep(
                    type="combat",
                    enemy="no-such-enemy",
                    on_win=OutcomeBranch(effects=[EndAdventureEffect(type="end_adventure", outcome="completed")]),
                    on_defeat=OutcomeBranch(effects=[EndAdventureEffect(type="end_adventure", outcome="defeated")]),
                    on_flee=OutcomeBranch(effects=[EndAdventureEffect(type="end_adventure", outcome="fled")]),
                )
            ],
        ),
    )
    registry = ContentRegistry.build(manifests=[region, location, adventure])
    issues = validate_semantic(registry)
    errors = [i for i in issues if i.severity == "error"]
    assert any("no-such-enemy" in i.message for i in errors)

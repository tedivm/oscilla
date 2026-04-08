"""Tests for semantic_validator.py."""

from __future__ import annotations

import pytest

from oscilla.engine.models.adventure import (
    AdventureManifest,
    AdventureSpec,
    CombatStep,
    EndAdventureEffect,
    NarrativeStep,
    OutcomeBranch,
)
from oscilla.engine.models.base import Metadata
from oscilla.engine.models.game import GameManifest, GameSpec, HpFormula
from oscilla.engine.models.location import LocationManifest, LocationSpec
from oscilla.engine.models.region import RegionManifest, RegionSpec
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.semantic_validator import SemanticIssue, validate_semantic


def _base_region(name: str = "forest") -> RegionManifest:
    return RegionManifest(
        apiVersion="oscilla/v1",
        kind="Region",
        metadata=Metadata(name=name),
        spec=RegionSpec(displayName=name.title()),
    )


def _base_location(name: str = "clearing", region: str = "forest") -> LocationManifest:
    return LocationManifest(
        apiVersion="oscilla/v1",
        kind="Location",
        metadata=Metadata(name=name),
        spec=LocationSpec(displayName=name.title(), region=region),
    )


def _base_adventure(name: str = "find-sword") -> AdventureManifest:
    return AdventureManifest(
        apiVersion="oscilla/v1",
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
        apiVersion="oscilla/v1",
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
        apiVersion="oscilla/v1",
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
        apiVersion="oscilla/v1",
        kind="Region",
        metadata=Metadata(name="forest"),
        spec=RegionSpec(displayName="Forest", parent="mountains"),
    )
    region_b = RegionManifest(
        apiVersion="oscilla/v1",
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


def test_triggered_adventure_is_not_orphaned() -> None:
    """An adventure wired to a trigger should not be flagged as orphaned."""
    region = _base_region()
    location = _base_location()  # no adventure pool entries
    adventure = _base_adventure("character-creation")
    game = GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(
            displayName="Test Game",
            xp_thresholds=[100],
            hp_formula=HpFormula(base_hp=10, hp_per_level=2),
            trigger_adventures={"on_character_create": ["character-creation"]},
        ),
    )
    registry = ContentRegistry.build(manifests=[region, location, adventure, game])
    issues = validate_semantic(registry)
    orphan_warnings = [i for i in issues if i.severity == "warning" and "character-creation" in i.message]
    assert orphan_warnings == [], f"Unexpected orphan warning for triggered adventure: {orphan_warnings}"


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
        apiVersion="oscilla/v1",
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


# ---------------------------------------------------------------------------
# Time system — semantic validator tests (tasks 12.1-12.4)
# ---------------------------------------------------------------------------


def _time_game(cycles: list, epoch: dict | None = None, eras: list | None = None) -> object:
    """Build a minimal GameManifest with a time block for validator testing."""
    from oscilla.engine.models.game import GameManifest, GameSpec

    return GameManifest(
        apiVersion="oscilla/v1",
        kind="Game",
        metadata=Metadata(name="test-game"),
        spec=GameSpec(
            displayName="Test",
            xp_thresholds=[0, 100],
            hp_formula={"base_hp": 10, "hp_per_level": 5},
            time={
                "ticks_per_adventure": 1,
                "base_unit": "tick",
                "pre_epoch_behavior": "clamp",
                "cycles": cycles,
                "epoch": epoch or {},
                "eras": eras or [],
            },
        ),
    )


# --- 12.1  Cycle DAG validation errors ---


def test_time_no_root_cycle_raises_error() -> None:
    """A time spec with no root cycle (type: ticks) must produce an error."""
    game = _time_game(
        cycles=[{"type": "cycle", "name": "hour", "parent": "tick", "count": 24}],
    )
    registry = ContentRegistry.build(manifests=[game])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("root" in i.message.lower() for i in errors)


def test_time_two_root_cycles_raises_error() -> None:
    """Two root cycles in a time spec must produce an error."""
    game = _time_game(
        cycles=[
            {"type": "ticks", "name": "tick-a"},
            {"type": "ticks", "name": "tick-b"},
        ],
    )
    registry = ContentRegistry.build(manifests=[game])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("root" in i.message.lower() for i in errors)


def test_time_circular_parent_reference_raises_error() -> None:
    """Two derived cycles that are each other's parent form a cycle — must be an error."""
    game = _time_game(
        cycles=[
            {"type": "ticks", "name": "tick"},
            {"type": "cycle", "name": "cycle-a", "parent": "cycle-b", "count": 2},
            {"type": "cycle", "name": "cycle-b", "parent": "cycle-a", "count": 3},
        ],
    )
    registry = ContentRegistry.build(manifests=[game])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("circular" in i.message.lower() for i in errors)


def test_time_unknown_parent_raises_error() -> None:
    """A derived cycle whose parent does not exist must produce an error."""
    game = _time_game(
        cycles=[
            {"type": "ticks", "name": "tick"},
            {"type": "cycle", "name": "hour", "parent": "no-such-cycle", "count": 24},
        ],
    )
    registry = ContentRegistry.build(manifests=[game])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("no-such-cycle" in i.message for i in errors)


def test_time_duplicate_cycle_name_raises_error() -> None:
    """Two cycles sharing a name must produce an error."""
    game = _time_game(
        cycles=[
            {"type": "ticks", "name": "tick"},
            {"type": "cycle", "name": "tick", "parent": "tick", "count": 4},
        ],
    )
    registry = ContentRegistry.build(manifests=[game])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("duplicate" in i.message.lower() or "tick" in i.message for i in errors)


def test_time_labels_length_mismatch_raises_error() -> None:
    """labels list length not matching count must produce an error.

    DerivedCycleSpec enforces this invariant via a Pydantic model_validator — the
    mismatch is caught at model construction time (before the semantic validator runs).
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="labels list has"):
        _time_game(
            cycles=[
                {"type": "ticks", "name": "tick"},
                {
                    "type": "cycle",
                    "name": "hour",
                    "parent": "tick",
                    "count": 4,
                    # Only 3 labels provided but count=4
                    "labels": ["Dawn", "Noon", "Dusk"],
                },
            ],
        )


# --- 12.2  Epoch validation errors ---


def test_time_epoch_nonexistent_cycle_raises_error() -> None:
    """An epoch entry referencing an undeclared cycle name must produce an error."""
    game = _time_game(
        cycles=[{"type": "ticks", "name": "tick"}],
        epoch={"ghost-cycle": 1},
    )
    registry = ContentRegistry.build(manifests=[game])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("ghost-cycle" in i.message for i in errors)


def test_time_epoch_invalid_label_raises_error() -> None:
    """An epoch entry with a string value not in the cycle's labels must produce an error."""
    game = _time_game(
        cycles=[
            {"type": "ticks", "name": "tick"},
            {
                "type": "cycle",
                "name": "season",
                "parent": "tick",
                "count": 4,
                "labels": ["Spring", "Summer", "Autumn", "Winter"],
            },
        ],
        epoch={"season": "MidWinter"},  # not a valid label
    )
    registry = ContentRegistry.build(manifests=[game])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("MidWinter" in i.message for i in errors)


def test_time_epoch_out_of_range_integer_raises_error() -> None:
    """An epoch integer outside the cycle's 1-based range must produce an error."""
    game = _time_game(
        cycles=[
            {"type": "ticks", "name": "tick"},
            {"type": "cycle", "name": "season", "parent": "tick", "count": 4},
        ],
        epoch={"season": 5},  # out of range; valid range is 1..4
    )
    registry = ContentRegistry.build(manifests=[game])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("season" in i.message for i in errors)


# --- 12.3  Era validation errors ---


def test_time_era_unknown_tracks_raises_error() -> None:
    """An era referencing an undeclared tracks cycle must produce an error."""
    game = _time_game(
        cycles=[{"type": "ticks", "name": "tick"}],
        eras=[
            {
                "name": "test-era",
                "format": "Year {count}",
                "epoch_count": 1,
                "tracks": "ghost-cycle",
            }
        ],
    )
    registry = ContentRegistry.build(manifests=[game])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("ghost-cycle" in i.message or "tracks" in i.message.lower() for i in errors)


# --- 12.4  Condition cross-reference validation ---


def test_time_condition_cycle_is_unknown_cycle_raises_error() -> None:
    """game_calendar_cycle_is referencing an unknown cycle name must produce an error."""
    game = _time_game(cycles=[{"type": "ticks", "name": "tick"}])
    adventure = AdventureManifest(
        apiVersion="oscilla/v1",
        kind="Adventure",
        metadata=Metadata(name="gated"),
        spec=AdventureSpec(
            displayName="Gated",
            steps=[NarrativeStep(type="narrative", text="ok.")],
            requires={"type": "game_calendar_cycle_is", "cycle": "ghost-cycle", "value": "Dawn"},
        ),
    )
    registry = ContentRegistry.build(manifests=[game, adventure])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("ghost-cycle" in i.message for i in errors)


def test_time_condition_cycle_is_invalid_label_raises_error() -> None:
    """game_calendar_cycle_is with a value not in the cycle's labels must produce an error."""
    game = _time_game(
        cycles=[
            {"type": "ticks", "name": "tick"},
            {
                "type": "cycle",
                "name": "season",
                "parent": "tick",
                "count": 4,
                "labels": ["Spring", "Summer", "Autumn", "Winter"],
            },
        ]
    )
    adventure = AdventureManifest(
        apiVersion="oscilla/v1",
        kind="Adventure",
        metadata=Metadata(name="gated"),
        spec=AdventureSpec(
            displayName="Gated",
            steps=[NarrativeStep(type="narrative", text="ok.")],
            requires={"type": "game_calendar_cycle_is", "cycle": "season", "value": "Monsoon"},
        ),
    )
    registry = ContentRegistry.build(manifests=[game, adventure])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("Monsoon" in i.message for i in errors)


def test_time_condition_era_is_unknown_era_raises_error() -> None:
    """game_calendar_era_is referencing an unknown era name must produce an error."""
    game = _time_game(cycles=[{"type": "ticks", "name": "tick"}])
    adventure = AdventureManifest(
        apiVersion="oscilla/v1",
        kind="Adventure",
        metadata=Metadata(name="gated"),
        spec=AdventureSpec(
            displayName="Gated",
            steps=[NarrativeStep(type="narrative", text="ok.")],
            requires={"type": "game_calendar_era_is", "era": "ghost-era", "state": "active"},
        ),
    )
    registry = ContentRegistry.build(manifests=[game, adventure])
    errors = [i for i in validate_semantic(registry) if i.severity == "error"]
    assert any("ghost-era" in i.message for i in errors)

"""Tests for the ContentGraph builders in oscilla/engine/graph.py."""

from __future__ import annotations

from oscilla.engine.graph import (
    build_adventure_graph,
    build_deps_graph,
    build_world_graph,
)
from oscilla.engine.models.adventure import (
    AdventureManifest,
    AdventureSpec,
    ChoiceOption,
    ChoiceStep,
    CombatStep,
    NarrativeStep,
    OutcomeBranch,
    StatCheckStep,
)
from oscilla.engine.models.base import LevelCondition, Metadata
from oscilla.engine.models.location import AdventurePoolEntry, LocationManifest, LocationSpec
from oscilla.engine.models.region import RegionManifest, RegionSpec
from oscilla.engine.registry import ContentRegistry


def _meta(name: str) -> Metadata:
    return Metadata(name=name)


def _make_minimal_registry() -> ContentRegistry:
    """Build a minimal ContentRegistry with one region, location, and adventure."""
    region = RegionManifest(
        apiVersion="game/v1",
        kind="Region",
        metadata=_meta("forest"),
        spec=RegionSpec(displayName="The Forest"),
    )
    location = LocationManifest(
        apiVersion="game/v1",
        kind="Location",
        metadata=_meta("clearing"),
        spec=LocationSpec(
            displayName="The Clearing",
            region="forest",
            adventures=[AdventurePoolEntry(ref="goblin-fight", weight=1)],
        ),
    )
    adventure = AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=_meta("goblin-fight"),
        spec=AdventureSpec(
            displayName="Goblin Fight",
            steps=[
                NarrativeStep(
                    type="narrative",
                    text="A goblin appears!",
                    effects=[],
                )
            ],
        ),
    )
    return ContentRegistry.build(manifests=[region, location, adventure])


def test_world_graph_has_region_node() -> None:
    registry = _make_minimal_registry()
    graph = build_world_graph(registry)
    node_ids = {n.id for n in graph.nodes}
    assert "region:forest" in node_ids


def test_world_graph_has_location_node() -> None:
    registry = _make_minimal_registry()
    graph = build_world_graph(registry)
    node_ids = {n.id for n in graph.nodes}
    assert "location:clearing" in node_ids


def test_world_graph_has_adventure_node() -> None:
    registry = _make_minimal_registry()
    graph = build_world_graph(registry)
    node_ids = {n.id for n in graph.nodes}
    assert "adventure:goblin-fight" in node_ids


def test_world_graph_location_connects_to_region() -> None:
    registry = _make_minimal_registry()
    graph = build_world_graph(registry)
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("region:forest", "location:clearing") in edges


def test_world_graph_adventure_pool_edge() -> None:
    registry = _make_minimal_registry()
    graph = build_world_graph(registry)
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("location:clearing", "adventure:goblin-fight") in edges


def test_world_graph_has_game_root_node() -> None:
    registry = _make_minimal_registry()
    graph = build_world_graph(registry)
    node_ids = {n.id for n in graph.nodes}
    assert "game:root" in node_ids


def test_world_graph_region_links_to_root_when_no_parent() -> None:
    registry = _make_minimal_registry()
    graph = build_world_graph(registry)
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("game:root", "region:forest") in edges


def test_world_graph_sub_region_links_to_parent() -> None:
    parent_region = RegionManifest(
        apiVersion="game/v1",
        kind="Region",
        metadata=_meta("outer"),
        spec=RegionSpec(displayName="Outer"),
    )
    child_region = RegionManifest(
        apiVersion="game/v1",
        kind="Region",
        metadata=_meta("inner"),
        spec=RegionSpec(displayName="Inner", parent="outer"),
    )
    registry = ContentRegistry.build(manifests=[parent_region, child_region])
    graph = build_world_graph(registry)
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("region:outer", "region:inner") in edges


def test_adventure_graph_has_start_node() -> None:
    registry = _make_minimal_registry()
    manifest = registry.adventures.get("goblin-fight")
    assert manifest is not None
    graph = build_adventure_graph(manifest, registry)
    node_ids = {n.id for n in graph.nodes}
    assert "start" in node_ids


def test_adventure_graph_has_narrative_node() -> None:
    registry = _make_minimal_registry()
    manifest = registry.adventures.get("goblin-fight")
    assert manifest is not None
    graph = build_adventure_graph(manifest, registry)
    kinds = {n.kind for n in graph.nodes}
    assert "narrative" in kinds


def test_adventure_graph_combat_branches() -> None:
    """CombatStep generates on_win, on_defeat, on_flee branches."""
    adventure = AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=_meta("combat-adv"),
        spec=AdventureSpec(
            displayName="Combat Adventure",
            steps=[CombatStep(type="combat", enemy="test-enemy")],
        ),
    )
    registry = ContentRegistry.build(manifests=[adventure])
    graph = build_adventure_graph(adventure, registry)
    edge_labels = {e.label for e in graph.edges}
    assert "on_win" in edge_labels
    assert "on_defeat" in edge_labels
    assert "on_flee" in edge_labels


def test_adventure_graph_choice_branches() -> None:
    """ChoiceStep generates one edge per option."""
    adventure = AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=_meta("choice-adv"),
        spec=AdventureSpec(
            displayName="Choice Adventure",
            steps=[
                ChoiceStep(
                    type="choice",
                    prompt="What do you do?",
                    options=[
                        ChoiceOption(label="Fight"),
                        ChoiceOption(label="Flee"),
                    ],
                )
            ],
        ),
    )
    registry = ContentRegistry.build(manifests=[adventure])
    graph = build_adventure_graph(adventure, registry)
    edge_labels = {e.label for e in graph.edges}
    assert "Fight" in edge_labels
    assert "Flee" in edge_labels


def test_adventure_graph_stat_check_branches() -> None:
    """StatCheckStep generates on_pass and on_fail branches."""
    adventure = AdventureManifest(
        apiVersion="game/v1",
        kind="Adventure",
        metadata=_meta("stat-adv"),
        spec=AdventureSpec(
            displayName="Stat Check Adventure",
            steps=[
                StatCheckStep(
                    type="stat_check",
                    condition=LevelCondition(type="level", value=5),
                    on_pass=OutcomeBranch(steps=[NarrativeStep(type="narrative", text="You passed!", effects=[])]),
                    on_fail=OutcomeBranch(steps=[NarrativeStep(type="narrative", text="You failed!", effects=[])]),
                )
            ],
        ),
    )
    registry = ContentRegistry.build(manifests=[adventure])
    graph = build_adventure_graph(adventure, registry)
    edge_labels = {e.label for e in graph.edges}
    assert "on_pass" in edge_labels
    assert "on_fail" in edge_labels


def test_deps_graph_has_location_and_region() -> None:
    registry = _make_minimal_registry()
    graph = build_deps_graph(registry)
    node_ids = {n.id for n in graph.nodes}
    assert "location:clearing" in node_ids
    assert "region:forest" in node_ids


def test_deps_graph_focus_filters_to_neighborhood() -> None:
    registry = _make_minimal_registry()
    graph = build_deps_graph(registry, focus="location:clearing")
    node_ids = {n.id for n in graph.nodes}
    # Focus node must be present
    assert "location:clearing" in node_ids
    # Its neighbor (adventure) must be present
    assert "adventure:goblin-fight" in node_ids


def test_deps_graph_include_kinds_filter() -> None:
    registry = _make_minimal_registry()
    graph = build_deps_graph(registry, include_kinds={"region"})
    kinds = {n.kind for n in graph.nodes}
    # Only regions should be present (and focus node if set; here no focus)
    assert kinds <= {"region"}


def test_deps_graph_exclude_kinds_filter() -> None:
    registry = _make_minimal_registry()
    graph = build_deps_graph(registry, exclude_kinds={"adventure"})
    node_ids = {n.id for n in graph.nodes}
    # Adventures should be excluded
    assert not any(nid.startswith("adventure:") for nid in node_ids)

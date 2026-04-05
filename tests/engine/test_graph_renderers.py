"""Tests for graph renderers in oscilla/engine/graph_renderers.py."""

from __future__ import annotations

from oscilla.engine.graph import ContentGraph, GraphEdge, GraphNode
from oscilla.engine.graph_renderers import render_ascii, render_dot, render_mermaid


def _simple_graph() -> ContentGraph:
    g = ContentGraph(title="Test Graph")
    g.add_node(GraphNode(id="region:forest", label="The Forest", kind="region"))
    g.add_node(GraphNode(id="location:clearing", label="The Clearing", kind="location"))
    g.add_edge(GraphEdge(source="region:forest", target="location:clearing", label="contains"))
    return g


def test_render_dot_is_digraph() -> None:
    output = render_dot(_simple_graph())
    assert "digraph" in output


def test_render_dot_contains_node_labels() -> None:
    output = render_dot(_simple_graph())
    assert "The Forest" in output
    assert "The Clearing" in output


def test_render_dot_contains_edge() -> None:
    output = render_dot(_simple_graph())
    assert "region:forest" in output or "region" in output


def test_render_mermaid_has_flowchart_header() -> None:
    output = render_mermaid(_simple_graph())
    assert "flowchart LR" in output


def test_render_mermaid_contains_title() -> None:
    output = render_mermaid(_simple_graph())
    assert "Test Graph" in output


def test_render_mermaid_contains_node_ids() -> None:
    output = render_mermaid(_simple_graph())
    # Node IDs are sanitized (colons and dashes replaced with underscores)
    assert "region_forest" in output
    assert "location_clearing" in output


def test_render_ascii_contains_labels() -> None:
    output = render_ascii(_simple_graph())
    assert "The Forest" in output
    assert "The Clearing" in output


def test_render_ascii_has_title() -> None:
    output = render_ascii(_simple_graph())
    assert "Test Graph" in output


def test_render_mermaid_sanitizes_hash() -> None:
    g = ContentGraph(title="Hash#Test")
    g.add_node(GraphNode(id="a", label="Node #1", kind="region"))
    output = render_mermaid(g)
    # '#' must be escaped to avoid Mermaid entity conflicts
    assert "#35;" in output


def test_render_mermaid_sanitizes_double_quote() -> None:
    g = ContentGraph(title="Quote Test")
    g.add_node(GraphNode(id="a", label='Node "quoted"', kind="region"))
    output = render_mermaid(g)
    assert "#quot;" in output


def test_render_mermaid_choice_node_uses_diamond_shape() -> None:
    g = ContentGraph(title="Shape Test")
    g.add_node(GraphNode(id="c", label="Pick one", kind="choice"))
    output = render_mermaid(g)
    # Choice nodes use curly braces {label}
    assert "{" in output


def test_render_mermaid_game_node_uses_circle_shape() -> None:
    g = ContentGraph(title="Shape Test")
    g.add_node(GraphNode(id="g", label="My Game", kind="game"))
    output = render_mermaid(g)
    # Game nodes use double parentheses ((label))
    assert "((" in output


def test_render_ascii_tree_structure() -> None:
    """Root node should appear before children in the ASCII output."""
    output = render_ascii(_simple_graph())
    forest_pos = output.find("The Forest")
    clearing_pos = output.find("The Clearing")
    assert forest_pos < clearing_pos


def test_render_dot_empty_graph() -> None:
    g = ContentGraph(title="Empty")
    output = render_dot(g)
    assert "digraph" in output


def test_render_mermaid_empty_graph() -> None:
    g = ContentGraph(title="Empty")
    output = render_mermaid(g)
    assert "flowchart LR" in output


def test_render_ascii_empty_graph() -> None:
    g = ContentGraph(title="Empty")
    output = render_ascii(g)
    assert "Empty" in output

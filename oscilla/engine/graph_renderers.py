"""Render a ContentGraph to DOT, Mermaid, or ASCII string output."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from oscilla.engine.graph import ContentGraph, GraphNode

GraphFormat = Literal["dot", "mermaid", "ascii"]


def _kind_colors() -> dict[str, str]:
    """Load graph node colors from settings.

    Deferred import prevents circular imports between settings and engine modules.
    """
    from oscilla.settings import settings

    return {
        "game": settings.graph_color_game,
        "region": settings.graph_color_region,
        "location": settings.graph_color_location,
        "adventure": settings.graph_color_adventure,
        "enemy": settings.graph_color_enemy,
        "item": settings.graph_color_item,
        "skill": settings.graph_color_skill,
        "buff": settings.graph_color_buff,
        "quest": settings.graph_color_quest,
        "recipe": settings.graph_color_recipe,
        "loot-table": settings.graph_color_loot_table,
        "start": settings.graph_color_start,
        "end": settings.graph_color_end,
        "goto": "#cccccc",
        "narrative": settings.graph_color_narrative,
        "combat": settings.graph_color_combat,
        "choice": settings.graph_color_choice,
        "stat_check": settings.graph_color_stat_check,
        "passive": settings.graph_color_passive,
    }


def render(graph: "ContentGraph", fmt: GraphFormat) -> str:
    """Dispatch to the appropriate renderer."""
    match fmt:
        case "dot":
            return render_dot(graph)
        case "mermaid":
            return render_mermaid(graph)
        case "ascii":
            return render_ascii(graph)
        case _:
            raise ValueError(f"Unknown format {fmt!r}. Valid: dot, mermaid, ascii")


def render_dot(graph: "ContentGraph") -> str:
    """Render to Graphviz DOT format using pydot.

    pydot is a thin wrapper over the DOT language; it does NOT require
    Graphviz to be installed. The output string can be piped to `dot -Tsvg`
    independently if the user has Graphviz available.
    """
    import pydot  # deferred — only imported when DOT output is requested

    colors = _kind_colors()
    dot_graph = pydot.Dot(graph_type="digraph", label=graph.title, fontname="sans-serif")
    dot_graph.set_graph_defaults(rankdir="LR", splines="ortho")
    dot_graph.set_node_defaults(shape="box", style="filled", fontname="sans-serif", fontsize="10")

    for node in graph.nodes:
        color = colors.get(node.kind, "#ffffff")
        dot_node = pydot.Node(
            _dot_id(node.id),
            label=node.label,
            fillcolor=color,
            tooltip=f"{node.kind}: {node.id}",
        )
        dot_graph.add_node(dot_node)

    for edge in graph.edges:
        dot_edge = pydot.Edge(
            _dot_id(edge.source),
            _dot_id(edge.target),
            label=edge.label,
            fontsize="9",
            fontname="sans-serif",
        )
        dot_graph.add_edge(dot_edge)

    return dot_graph.to_string()


def _dot_id(node_id: str) -> str:
    """Sanitize a node id for use as a DOT identifier."""
    return '"' + node_id.replace('"', '\\"') + '"'


def _sanitize_mermaid_label(text: str) -> str:
    """Sanitize a label string for safe use inside a quoted Mermaid node label.

    Mermaid uses quoted labels to allow most characters, but certain sequences
    can still break the parser. The safe rules applied here:
    - Replace '#' with '#35;' to prevent false entity-code interpretation.
    - Replace '"' with '#quot;' (Mermaid entity code for double-quote).
    - Remove or replace characters that cannot be safely embedded even in
      quoted context: backticks (trigger Markdown mode) and newlines.
    """
    text = text.replace("#", "#35;")  # escape '#' before any entity codes
    text = text.replace('"', "#quot;")  # entity code for double-quote
    text = text.replace("`", "'")  # backtick triggers Markdown mode
    text = text.replace("\n", " ").replace("\r", " ")  # flatten multiline
    return text


def render_mermaid(graph: "ContentGraph") -> str:
    """Render to Mermaid flowchart syntax (LR direction).

    Output is compatible with GitHub Markdown, mkdocs-material, and the
    Mermaid Live Editor at mermaid.live.

    Labels are sanitized with _sanitize_mermaid_label() to prevent parser
    errors from special characters. Node IDs are derived from manifest
    kind:name slugs and are always safe (alphanumeric + underscore only).
    """
    lines = ["---", f'title: "{graph.title}"', "---", "flowchart LR"]

    # Node declarations with shape by kind
    for node in graph.nodes:
        safe_id = _mermaid_id(node.id)
        safe_label = _sanitize_mermaid_label(node.label)
        shape_open, shape_close = _mermaid_shape(node.kind)
        lines.append(f'    {safe_id}{shape_open}"{safe_label}"{shape_close}')

    lines.append("")

    # Edges
    for edge in graph.edges:
        src = _mermaid_id(edge.source)
        tgt = _mermaid_id(edge.target)
        lbl = _sanitize_mermaid_label(edge.label) if edge.label else ""
        arrow = f"-- {lbl} -->" if lbl else "-->"
        lines.append(f"    {src} {arrow} {tgt}")

    return "\n".join(lines)


def _mermaid_id(node_id: str) -> str:
    """Convert a node id to a valid Mermaid identifier."""
    return node_id.replace(":", "_").replace("-", "_").replace(" ", "_")


def _mermaid_shape(kind: str) -> tuple[str, str]:
    """Return Mermaid shape brackets for a node kind."""
    match kind:
        case "start" | "end":
            return "([", "])"
        case "choice":
            return "{", "}"
        case "combat":
            return "[/", "/]"
        case "game":
            return "((", "))"
        case _:
            return "[", "]"


def render_ascii(graph: "ContentGraph") -> str:
    """Render as a tree using ASCII box-drawing characters.

    For world graphs, builds a proper hierarchy tree.
    For adventure and dep graphs, falls back to a flat adjacency list
    since arbitrary DAGs are hard to present as a clean tree.
    """
    # Build adjacency list: parent → children
    children: dict[str, list[str]] = {}
    all_targets: set[str] = set()
    for edge in graph.edges:
        children.setdefault(edge.source, []).append(edge.target)
        all_targets.add(edge.target)

    # Find root nodes (nodes with no incoming edges)
    all_ids = {n.id for n in graph.nodes}
    roots = sorted(all_ids - all_targets)
    node_map = {n.id: n for n in graph.nodes}

    lines = [f"# {graph.title}", ""]

    if not roots:
        # Fallback for cyclic or edge-only graphs
        for node in graph.nodes:
            lines.append(f"  {node.kind}: {node.label} [{node.id}]")
        return "\n".join(lines)

    def _draw_tree(node_id: str, prefix: str, is_last: bool) -> None:
        node = node_map.get(node_id)
        label = node.label if node else node_id
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{label}")
        kids = children.get(node_id, [])
        child_prefix = prefix + ("    " if is_last else "│   ")
        for i, kid in enumerate(kids):
            _draw_tree(kid, child_prefix, i == len(kids) - 1)

    for i, root in enumerate(roots):
        root_node: GraphNode | None = node_map.get(root)
        lines.append(root_node.label if root_node else root)
        kids = children.get(root, [])
        for j, kid in enumerate(kids):
            _draw_tree(kid, "", j == len(kids) - 1)
        if i < len(roots) - 1:
            lines.append("")

    return "\n".join(lines)

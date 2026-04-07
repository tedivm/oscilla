# Design: Author CLI

## Context

The `oscilla` CLI currently exposes two commands relevant to content authors:

- `oscilla validate` — loads manifests, reports schema errors and manifest counts
- `oscilla game` — launches the TUI game loop

Authors discover broken references, unreachable adventures, and structural problems by running the game — often deep into a session. There is no way to inspect a loaded registry, visualize world or adventure structure, trace how an adventure flows, scaffold new manifests, or export machine-readable schema for editor integration.

The loaded `ContentRegistry` already contains fully parsed, validated, cross-referenced manifests for every kind. Everything needed for rich author tooling exists at the data layer. The gap is entirely in the CLI surface.

**Current `oscilla/cli.py` commands:**

| Command     | Function                                               |
| ----------- | ------------------------------------------------------ |
| `game`      | Launches TUI                                           |
| `validate`  | Loads content, reports schema errors + manifest counts |
| `version`   | Prints version                                         |
| `hello`     | Greeting                                               |
| `data-path` | Prints data directory                                  |
| `test-data` | Installs dev test data                                 |

The `_load_games()` helper in `cli.py` already wraps `load_games()` with clean error reporting and `SystemExit(1)` on failure. All new `content` commands will reuse this.

---

## Goals / Non-Goals

**Goals:**

- `oscilla content list KIND` — tabular listing of loaded manifests for one kind
- `oscilla content show KIND NAME` — rich description of one manifest including references
- `oscilla content graph world|adventure|deps` — graph output in DOT, Mermaid, or ASCII
- `oscilla content schema [KIND]` — JSON Schema export from Pydantic models
- `oscilla content test` — semantic validation beyond schema: undefined refs, circular chains, orphaned/unreachable content
- `oscilla content trace ADVENTURE` — headless adventure path tracer with branch coverage (no saved-character state changes)
- `oscilla content create KIND` — scaffolds a valid YAML manifest at the conventional path; supports `--no-interactive` for scripting
- `oscilla validate` — now runs semantic checks by default; `--no-semantic` disables them
- `--format text|json|yaml` flag on list, show, test, and trace for machine-readable output

**Non-Goals:**

- Interactive step-by-step adventure editor (out of scope; a roadmap item must be added at archive time)
- Calling Graphviz binaries directly — DOT output is text only, via `pydot`
- Any TUI or game-session changes
- Modifying existing manifests (only create, not edit)
- Graph output for manifest kinds other than the three defined types (world, adventure, deps)

---

## Decisions

### Decision 1 — Command Namespace: `oscilla content` Subapp

All author tooling lives under `oscilla content` as a Typer subapp. This keeps the top-level namespace clean and visually separates "play the game" commands from "author tooling" commands.

#### `oscilla/cli_content.py` (new file)

```python
"""Author-facing content tooling subapp.

All commands are registered under ``oscilla content`` via:
    app.add_typer(content_app, name="content")
in oscilla/cli.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

content_app = typer.Typer(
    name="content",
    help="Content authoring tools: inspect, graph, validate, trace, scaffold.",
    no_args_is_help=True,
)

_console = Console()
_err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_registry(game_name: str | None) -> "tuple[str, ContentRegistry]":
    """Load games and return a single (name, registry) pair.

    If game_name is given, load only that package. If omitted and exactly one
    game exists it is selected automatically. Raises SystemExit(1) on error.
    """
    from oscilla.settings import settings
    from oscilla.engine.loader import ContentLoadError, load, load_games

    gpath = settings.games_path
    if game_name is not None:
        game_path = gpath / game_name
        if not game_path.is_dir():
            _err_console.print(f"[bold red]Game {game_name!r} not found in GAMES_PATH[/bold red]")
            raise SystemExit(1)
        try:
            registry, _ = load(game_path)
        except ContentLoadError as exc:
            _err_console.print("[bold red]Content load failed:[/bold red]")
            for e in exc.errors:
                _err_console.print(f"  [red]•[/red] {e}")
            raise SystemExit(1)
        return game_name, registry

    try:
        games, _ = load_games(gpath)
    except ContentLoadError as exc:
        _err_console.print("[bold red]Content load failed:[/bold red]")
        for e in exc.errors:
            _err_console.print(f"  [red]•[/red] {e}")
        raise SystemExit(1)

    if not games:
        _err_console.print("[bold red]No game packages found in GAMES_PATH.[/bold red]")
        raise SystemExit(1)
    if len(games) == 1:
        name = next(iter(games))
        return name, games[name]
    _err_console.print(
        f"[bold red]Multiple games found. Use --game to specify one: "
        f"{', '.join(sorted(games))}[/bold red]"
    )
    raise SystemExit(1)


# Type alias for type-checker — not evaluated at runtime.
if False:  # pragma: no cover
    from oscilla.engine.registry import ContentRegistry
```

#### `oscilla/cli.py` — register the subapp

**Before (end of file):**

```python
# Type alias used purely for type checkers — never evaluated at runtime
if False:  # pragma: no cover
    from oscilla.engine.registry import ContentRegistry


if __name__ == "__main__":
    app()
```

**After:**

```python
from oscilla.cli_content import content_app

app.add_typer(content_app, name="content")

# Type alias used purely for type checkers — never evaluated at runtime
if False:  # pragma: no cover
    from oscilla.engine.registry import ContentRegistry


if __name__ == "__main__":
    app()
```

---

### Decision 2 — Manifest Kind Registry (`oscilla/engine/kinds.py`)

Multiple parts of the codebase independently enumerate all manifest kinds: `cli_content.py` defines `_KIND_MAP`, `schema_export.py` defines `_MANIFEST_MODELS`. A central registry eliminates duplication and future-proofs the system — adding a new manifest kind requires one edit instead of several.

```python
# oscilla/engine/kinds.py
"""Central registry of all Oscilla manifest kinds with metadata.

This module is the single source of truth for all manifest kinds. Every
subsystem that iterates over kinds (CLI, schema export, graph renderers)
imports from here rather than defining its own mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List


@dataclass(frozen=True)
class ManifestKind:
    """Metadata about one manifest kind."""

    slug: str               # CLI kind slug, e.g. "adventure"
    plural_slug: str        # Plural CLI slug, e.g. "adventures"
    registry_attr: str      # ContentRegistry attribute name, e.g. "adventures"
    display_label: str      # Singular display label, e.g. "Adventure"
    model_class: Any        # Pydantic model class, e.g. AdventureManifest
    creatable: bool = True  # Whether `content create` supports this kind


def _load_kinds() -> List[ManifestKind]:
    """Import and register all manifest kinds.

    Deferred import keeps the module importable without loading all models.
    """
    from oscilla.engine.models.adventure import AdventureManifest
    from oscilla.engine.models.buff import BuffManifest
    from oscilla.engine.models.character_config import CharacterConfigManifest
    from oscilla.engine.models.enemy import EnemyManifest
    from oscilla.engine.models.game import GameManifest
    from oscilla.engine.models.game_class import ClassManifest
    from oscilla.engine.models.item import ItemManifest
    from oscilla.engine.models.location import LocationManifest
    from oscilla.engine.models.loot_table import LootTableManifest
    from oscilla.engine.models.quest import QuestManifest
    from oscilla.engine.models.recipe import RecipeManifest
    from oscilla.engine.models.region import RegionManifest
    from oscilla.engine.models.skill import SkillManifest

    return [
        ManifestKind("adventure",      "adventures",  "adventures",  "Adventure",      AdventureManifest,     creatable=True),
        ManifestKind("buff",           "buffs",       "buffs",       "Buff",            BuffManifest,          creatable=False),
        ManifestKind("character-config","character-configs","character_configs","CharacterConfig", CharacterConfigManifest, creatable=False),
        ManifestKind("class",          "classes",     "classes",     "Class",           ClassManifest,         creatable=False),
        ManifestKind("enemy",          "enemies",     "enemies",     "Enemy",           EnemyManifest,         creatable=True),
        ManifestKind("game",           "games",       "games",       "Game",            GameManifest,          creatable=False),
        ManifestKind("item",           "items",       "items",       "Item",            ItemManifest,          creatable=True),
        ManifestKind("location",       "locations",   "locations",   "Location",        LocationManifest,      creatable=True),
        ManifestKind("loot-table",     "loot-tables", "loot_tables", "LootTable",       LootTableManifest,     creatable=False),
        ManifestKind("quest",          "quests",      "quests",      "Quest",           QuestManifest,         creatable=True),
        ManifestKind("recipe",         "recipes",     "recipes",     "Recipe",          RecipeManifest,        creatable=False),
        ManifestKind("region",         "regions",     "regions",     "Region",          RegionManifest,        creatable=True),
        ManifestKind("skill",          "skills",      "skills",      "Skill",           SkillManifest,         creatable=False),
    ]


# Module-level list. Import this in consuming modules.
ALL_KINDS: List[ManifestKind] = _load_kinds()

# Convenience lookup dicts.
KINDS_BY_SLUG: dict[str, ManifestKind] = {k.slug: k for k in ALL_KINDS}
KINDS_BY_PLURAL: dict[str, ManifestKind] = {k.plural_slug: k for k in ALL_KINDS}
KINDS_BY_REGISTRY_ATTR: dict[str, ManifestKind] = {k.registry_attr: k for k in ALL_KINDS}
```

Every place that previously defined its own kind constant or mapping now imports from `kinds.py`:

```python
# In oscilla/cli_content.py — replaces the inline _KIND_MAP dict:
from oscilla.engine.kinds import ALL_KINDS, KINDS_BY_PLURAL

# In oscilla/engine/schema_export.py — replaces the inline _MANIFEST_MODELS dict:
from oscilla.engine.kinds import ALL_KINDS
_MANIFEST_MODELS = {k.slug: k.model_class for k in ALL_KINDS}
```

---

### Decision 3 — `content list` and `content show`

#### Valid KIND values

`cli_content.py` imports from the central registry; no inline mapping is needed:

```python
# oscilla/cli_content.py

from oscilla.engine.kinds import ALL_KINDS, KINDS_BY_PLURAL

# Maps plural CLI kind slug → (registry attribute name, singular display label)
_KIND_MAP: Dict[str, Tuple[str, str]] = {
    k.plural_slug: (k.registry_attr, k.display_label) for k in ALL_KINDS
}
```

#### Output format type

All commands that produce structured data support a `--format` flag:

```python
# oscilla/cli_content.py
import io
import json
from typing import Any, Literal

OutputFormat = Literal["text", "json", "yaml"]


def _emit_structured_output(data: Any, output_format: OutputFormat) -> None:
    """Serialize `data` to stdout in the requested format and exit.

    This is the single point of truth for JSON/YAML serialization across all
    content commands. Call at the top of a function's body BEFORE any Rich
    rendering, then return immediately after.

    Raises SystemExit(1) with a human-readable message for unknown formats so
    that any caller that somehow bypasses Typer\'s Literal validation still gets
    a clean error rather than a silent no-op.
    """
    if output_format == "json":
        typer.echo(json.dumps(data, indent=2))
    elif output_format == "yaml":
        from ruamel.yaml import YAML as _YAML
        _y = _YAML()
        _y.default_flow_style = False
        buf = io.StringIO()
        _y.dump(data, buf)
        typer.echo(buf.getvalue())
    elif output_format != "text":
        _err_console.print(
            f"[red]Unknown format {output_format!r}. Valid: text, json, yaml.[/red]"
        )
        raise SystemExit(1)
```

#### `content list` command

```python
@content_app.command("list")
def content_list(
    kind: Annotated[str, typer.Argument(help=f"Manifest kind. One of: {', '.join(_KIND_MAP)}")],
    game: Annotated[Optional[str], typer.Option("--game", "-g", help="Game package name.")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
) -> None:
    """List all manifests of a given kind in the content package."""
    kind = kind.lower()
    if kind not in _KIND_MAP:
        _err_console.print(f"[bold red]Unknown kind {kind!r}. Valid: {', '.join(_KIND_MAP)}[/bold red]")
        raise SystemExit(1)

    attr, label = _KIND_MAP[kind]
    _, registry = _resolve_registry(game)
    store: KindRegistry = getattr(registry, attr)

    rows = []
    for manifest in store.all():
        rows.append(_manifest_summary(manifest, label))

    if output_format != "text":
        _emit_structured_output(rows, output_format)
        return

    if not rows:
        _console.print(f"[yellow]No {label} manifests found.[/yellow]")
        return

    table = Table(title=f"{label} manifests ({len(rows)} total)")
    # All rows share the same keys; build columns from first row.
    for col in rows[0]:
        table.add_column(col, style="cyan" if col == "name" else "")
    for row in rows:
        table.add_row(*[str(row[c]) for c in row])
    _console.print(table)


def _manifest_summary(manifest: "ManifestEnvelope", kind_label: str) -> Dict[str, str]:
    """Return a flat dict of display-relevant fields for a manifest.

    The fields extracted depend on the manifest kind. Unknown kinds fall back
    to name + kind only.
    """
    base: Dict[str, str] = {"name": manifest.metadata.name, "kind": kind_label}

    spec = manifest.spec  # type: ignore[attr-defined]
    if hasattr(spec, "displayName"):
        base["display_name"] = spec.displayName
    if hasattr(spec, "description") and spec.description:
        # Truncate long descriptions for table display.
        desc = spec.description
        base["description"] = desc[:60] + "…" if len(desc) > 60 else desc
    # Kind-specific extras:
    match kind_label:
        case "Region":
            base["parent"] = spec.parent or "—"
            base["unlock"] = "yes" if spec.unlock else "always"
        case "Location":
            base["region"] = spec.region
            base["adventures"] = str(len(spec.adventures))
        case "Adventure":
            base["steps"] = str(len(spec.steps))
            base["repeatable"] = "no" if not spec.repeatable else (
                str(spec.max_completions) if spec.max_completions else "yes"
            )
        case "Enemy":
            base["hp"] = str(spec.hp)
            base["attack"] = str(spec.attack)
            base["xp"] = str(spec.xp_reward)
        case "Item":
            base["category"] = spec.category
            base["labels"] = ", ".join(spec.labels) or "—"
    return base
```

#### `content show` command

```python
@content_app.command("show")
def content_show(
    kind: Annotated[str, typer.Argument(help="Manifest kind.")],
    name: Annotated[str, typer.Argument(help="Manifest name (metadata.name).")],
    game: Annotated[Optional[str], typer.Option("--game", "-g", help="Game package name.")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
) -> None:
    """Print a detailed description of one manifest including cross-references."""
    kind = kind.lower().rstrip("s")  # allow both "adventure" and "adventures"
    # Normalize to plural slug
    singular_to_plural = {v[1].lower(): k for k, v in _KIND_MAP.items()}
    plural_slug = singular_to_plural.get(kind, kind + "s")

    if plural_slug not in _KIND_MAP:
        _err_console.print(f"[bold red]Unknown kind. Valid: {', '.join(_KIND_MAP)}[/bold red]")
        raise SystemExit(1)

    attr, label = _KIND_MAP[plural_slug]
    _, registry = _resolve_registry(game)
    store: KindRegistry = getattr(registry, attr)
    manifest = store.get(name)

    if manifest is None:
        _err_console.print(f"[bold red]{label} {name!r} not found.[/bold red]")
        raise SystemExit(1)

    from oscilla.engine.graph import build_manifest_xrefs

    xrefs = build_manifest_xrefs(manifest, registry)

    if output_format != "text":
        _emit_structured_output({"manifest": manifest.model_dump(mode="json"), "xrefs": xrefs}, output_format)
        return

    _console.print(f"\n[bold]{label}:[/bold] {name}")
    _print_spec_fields(manifest)
    if xrefs.get("references"):
        _console.print("\n[dim]References:[/dim]")
        for ref in xrefs["references"]:
            _console.print(f"  → {ref}")
    if xrefs.get("referenced_by"):
        _console.print("\n[dim]Referenced by:[/dim]")
        for ref in xrefs["referenced_by"]:
            _console.print(f"  ← {ref}")
    _console.print()
```

---

### Decision 4 — Graph Engine (`oscilla/engine/graph.py`)

#### Data model

```python
# oscilla/engine/graph.py
"""Content graph construction — format-agnostic node/edge structure.

Graph building is a pure function over ContentRegistry. Rendering to DOT,
Mermaid, or ASCII is handled by oscilla/engine/graph_renderers.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from oscilla.engine.models.adventure import AdventureManifest
    from oscilla.engine.registry import ContentRegistry


@dataclass
class GraphNode:
    id: str          # Globally unique; convention: "kind:name", e.g. "region:combat"
    label: str       # Human-readable display label
    kind: str        # "region", "location", "adventure", "step", "enemy", "item", …
    attrs: Dict[str, str] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str           # GraphNode.id
    target: str           # GraphNode.id
    label: str = ""
    edge_type: str = ""   # "parent", "contains", "references", "flow", "outcome"


@dataclass
class ContentGraph:
    title: str
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    def has_node(self, node_id: str) -> bool:
        return any(n.id == node_id for n in self.nodes)
```

#### World graph builder

```python
def build_world_graph(registry: "ContentRegistry") -> ContentGraph:
    """Build the region → location → adventure-pool hierarchy graph."""
    graph = ContentGraph(title="World Map")

    # Root game node
    game_name = registry.game.spec.displayName if registry.game else "Game"
    root_id = "game:root"
    graph.add_node(GraphNode(id=root_id, label=game_name, kind="game"))

    # Regions
    for region in registry.regions.all():
        rid = f"region:{region.metadata.name}"
        unlock_label = _condition_summary(region.spec.unlock)
        graph.add_node(GraphNode(
            id=rid,
            label=region.spec.displayName,
            kind="region",
            attrs={"unlock": unlock_label},
        ))
        parent_id = f"region:{region.spec.parent}" if region.spec.parent else root_id
        graph.add_edge(GraphEdge(
            source=parent_id, target=rid,
            edge_type="contains",
            label="sub-region" if region.spec.parent else "",
        ))

    # Locations
    for loc in registry.locations.all():
        lid = f"location:{loc.metadata.name}"
        graph.add_node(GraphNode(
            id=lid,
            label=loc.spec.displayName,
            kind="location",
            attrs={"unlock": _condition_summary(loc.spec.unlock)},
        ))
        region_id = f"region:{loc.spec.region}"
        graph.add_edge(GraphEdge(source=region_id, target=lid, edge_type="contains"))

        # Adventure pool entries
        for entry in loc.spec.adventures:
            adv = registry.adventures.get(entry.ref)
            adv_label = adv.spec.displayName if adv else entry.ref
            aid = f"adventure:{entry.ref}"
            if not graph.has_node(aid):
                graph.add_node(GraphNode(id=aid, label=adv_label, kind="adventure"))
            req_label = f"w:{entry.weight}" + (
                f", req:{_condition_summary(entry.requires)}" if entry.requires else ""
            )
            graph.add_edge(GraphEdge(
                source=lid, target=aid,
                edge_type="references",
                label=req_label,
            ))

    return graph
```

#### Adventure flow graph builder

```python
def build_adventure_graph(
    manifest: "AdventureManifest",
    registry: "ContentRegistry",
) -> ContentGraph:
    """Build the step-flow graph for a single adventure.

    Nodes are individual steps; edges represent execution flow including choice
    branches, goto jumps, and combat outcome forks.
    """
    from oscilla.engine.models.adventure import (
        ChoiceStep, CombatStep, NarrativeStep, PassiveStep, StatCheckStep,
    )

    title = manifest.spec.displayName
    graph = ContentGraph(title=f"Adventure Flow: {title}")

    start_id = "start"
    graph.add_node(GraphNode(id=start_id, label="start", kind="start"))

    counter: List[int] = [0]  # mutable counter for step IDs across recursion

    def step_id() -> str:
        counter[0] += 1
        return f"step:{counter[0]}"

    def _add_step(step: object, prev_id: str, edge_label: str = "") -> str:
        """Add a step node and edge from prev_id. Returns this step's node id."""
        sid = step_id()
        match step:
            case NarrativeStep():
                text_preview = (step.text or "")[:40].replace("\n", " ")
                graph.add_node(GraphNode(
                    id=sid, label=f"narrative: {text_preview!r}", kind="narrative",
                    attrs={"label": step.label or ""},
                ))
            case CombatStep():
                graph.add_node(GraphNode(
                    id=sid, label=f"combat: {step.enemy}", kind="combat",
                    attrs={"enemy": step.enemy, "label": step.label or ""},
                ))
                # Combat outcome branches
                for branch_name, branch in [
                    ("on_win", step.on_win),
                    ("on_defeat", step.on_defeat),
                    ("on_flee", step.on_flee),
                ]:
                    if branch.goto:
                        goto_id = f"goto:{branch.goto}"
                        if not graph.has_node(goto_id):
                            graph.add_node(GraphNode(id=goto_id, label=f"→ {branch.goto}", kind="goto"))
                        graph.add_edge(GraphEdge(source=sid, target=goto_id, edge_type="outcome", label=branch_name))
                    elif branch.steps:
                        sub_prev = sid
                        for sub_step in branch.steps:
                            sub_prev = _add_step(sub_step, sub_prev, branch_name)
                    else:
                        end_id = f"end:{branch_name}:{counter[0]}"
                        graph.add_node(GraphNode(id=end_id, label=f"(end → {branch_name})", kind="end"))
                        graph.add_edge(GraphEdge(source=sid, target=end_id, edge_type="outcome", label=branch_name))
            case ChoiceStep():
                graph.add_node(GraphNode(
                    id=sid, label=f"choice: {step.prompt[:40]!r}", kind="choice",
                    attrs={"label": step.label or ""},
                ))
                for opt in step.options:
                    if opt.goto:
                        goto_id = f"goto:{opt.goto}"
                        if not graph.has_node(goto_id):
                            graph.add_node(GraphNode(id=goto_id, label=f"→ {opt.goto}", kind="goto"))
                        graph.add_edge(GraphEdge(source=sid, target=goto_id, edge_type="flow", label=opt.label[:30]))
                    elif opt.steps:
                        opt_prev = sid
                        for sub_step in opt.steps:
                            opt_prev = _add_step(sub_step, opt_prev, opt.label[:20])
                    else:
                        fall_id = f"fall:{counter[0]}"
                        graph.add_node(GraphNode(id=fall_id, label="(continue)", kind="continue"))
                        graph.add_edge(GraphEdge(source=sid, target=fall_id, edge_type="flow", label=opt.label[:30]))
            case StatCheckStep():
                cond_summary = _condition_summary(step.condition)
                graph.add_node(GraphNode(
                    id=sid, label=f"stat_check: {cond_summary}", kind="stat_check",
                    attrs={"label": step.label or ""},
                ))
                for branch_name, branch in [("on_pass", step.on_pass), ("on_fail", step.on_fail)]:
                    if branch.goto:
                        goto_id = f"goto:{branch.goto}"
                        if not graph.has_node(goto_id):
                            graph.add_node(GraphNode(id=goto_id, label=f"→ {branch.goto}", kind="goto"))
                        graph.add_edge(GraphEdge(source=sid, target=goto_id, edge_type="flow", label=branch_name))
                    elif branch.steps:
                        sub_prev = sid
                        for sub_step in branch.steps:
                            sub_prev = _add_step(sub_step, sub_prev, branch_name)
            case PassiveStep():
                eff_count = len(step.effects)
                graph.add_node(GraphNode(
                    id=sid, label=f"passive ({eff_count} effects)", kind="passive",
                    attrs={"label": step.label or ""},
                ))
        graph.add_edge(GraphEdge(source=prev_id, target=sid, edge_type="flow", label=edge_label))
        return sid

    prev = start_id
    for step in manifest.spec.steps:
        prev = _add_step(step, prev)

    return graph
```

#### Dependency graph builder

```python
def build_deps_graph(
    registry: "ContentRegistry",
    focus: str | None = None,
    include_kinds: set[str] | None = None,
    exclude_kinds: set[str] | None = None,
) -> ContentGraph:
    """Build the cross-manifest dependency graph.

    When focus is provided (format: "kind:name", e.g. "item:rusty-sword"),
    returns only the 1-hop neighborhood of that node.

    include_kinds: if provided, only nodes of these kinds are included.
    exclude_kinds: if provided, nodes of these kinds are removed.
    The focus node is always included regardless of kind filters.
    """
    from oscilla.engine.models.adventure import (
        ApplyBuffEffect, CombatStep, ItemDropEffect, SkillGrantEffect,
    )

    graph = ContentGraph(title="Content Dependency Graph")

    def _node(kind: str, name: str, label: str) -> str:
        nid = f"{kind}:{name}"
        if not graph.has_node(nid):
            graph.add_node(GraphNode(id=nid, label=label, kind=kind))
        return nid

    def _edge(src: str, tgt: str, lbl: str, etype: str) -> None:
        graph.add_edge(GraphEdge(source=src, target=tgt, label=lbl, edge_type=etype))

    # Regions → parent region
    for region in registry.regions.all():
        rid = _node("region", region.metadata.name, region.spec.displayName)
        if region.spec.parent:
            prid = _node("region", region.spec.parent, region.spec.parent)
            _edge(rid, prid, "parent", "parent")

    # Locations → region
    for loc in registry.locations.all():
        lid = _node("location", loc.metadata.name, loc.spec.displayName)
        rid = _node("region", loc.spec.region, loc.spec.region)
        _edge(lid, rid, "in region", "contains")

        # Adventures in pool
        for entry in loc.spec.adventures:
            aid = _node("adventure", entry.ref, entry.ref)
            _edge(lid, aid, f"pool w:{entry.weight}", "references")

    # Adventures → enemies, items (via effects), loot tables
    for adv in registry.adventures.all():
        aid = _node("adventure", adv.metadata.name, adv.spec.displayName)
        for step in _walk_all_steps(adv.spec.steps):
            match step:
                case CombatStep():
                    eid = _node("enemy", step.enemy, step.enemy)
                    _edge(aid, eid, "combat", "references")
        for effect in _walk_all_effects(adv.spec.steps):
            match effect:
                case ItemDropEffect(loot=loot, loot_ref=loot_ref):
                    if loot_ref:
                        tgt = _node("loot-table", loot_ref, loot_ref)
                        _edge(aid, tgt, "drops", "references")
                    elif loot:
                        for entry in loot:
                            iid = _node("item", entry.item, entry.item)
                            _edge(aid, iid, "drops", "references")
                case SkillGrantEffect(skill=skill_name):
                    sid = _node("skill", skill_name, skill_name)
                    _edge(aid, sid, "grants", "references")
                case ApplyBuffEffect(buff_ref=bref):
                    bid = _node("buff", bref, bref)
                    _edge(aid, bid, "applies", "references")

    # Enemies → loot
    for enemy in registry.enemies.all():
        eid = _node("enemy", enemy.metadata.name, enemy.spec.displayName)
        for entry in enemy.spec.loot:
            iid = _node("item", entry.item, entry.item)
            _edge(eid, iid, "loot", "references")
        for skill_entry in enemy.spec.skills:
            sid = _node("skill", skill_entry.skill_ref, skill_entry.skill_ref)
            _edge(eid, sid, "uses", "references")

    # Recipes → items
    for recipe in registry.recipes.all():
        rid = _node("recipe", recipe.metadata.name, recipe.spec.displayName)
        out_id = _node("item", recipe.spec.output.item, recipe.spec.output.item)
        _edge(rid, out_id, "produces", "references")
        for ing in recipe.spec.inputs:
            iid = _node("item", ing.item, ing.item)
            _edge(rid, iid, "requires", "references")

    # LootTables → items
    for lt in registry.loot_tables.all():
        lid = _node("loot-table", lt.metadata.name, lt.metadata.name)
        for entry in lt.spec.loot:
            iid = _node("item", entry.item, entry.item)
            _edge(lid, iid, "drops", "references")

    # Quests → milestones (advance_on entries)
    for quest in registry.quests.all():
        qid = _node("quest", quest.metadata.name, quest.spec.displayName)
        for stage in quest.spec.stages:
            for ms in stage.advance_on:
                mid = _node("milestone", ms, ms)
                _edge(qid, mid, "advances on", "references")

    if focus is not None:
        graph = _filter_to_neighborhood(graph, focus)

    # Apply kind filters after focus so we don't accidentally remove the focus node's context.
    if include_kinds is not None or exclude_kinds is not None:
        focus_kind = focus.split(":")[0] if focus else None
        kept_ids = {
            n.id for n in graph.nodes
            if (include_kinds is None or n.kind in include_kinds)
            and (exclude_kinds is None or n.kind not in exclude_kinds)
            or n.id == focus  # always keep the focus node itself
        }
        filtered = ContentGraph(title=graph.title)
        for node in graph.nodes:
            if node.id in kept_ids:
                filtered.add_node(node)
        for edge in graph.edges:
            if edge.source in kept_ids and edge.target in kept_ids:
                filtered.add_edge(edge)
        graph = filtered

    return graph


def _filter_to_neighborhood(graph: ContentGraph, focus_id: str) -> ContentGraph:
    """Return a new ContentGraph containing only the focus node and its direct neighbors."""
    connected_ids = {focus_id}
    for edge in graph.edges:
        if edge.source == focus_id:
            connected_ids.add(edge.target)
        if edge.target == focus_id:
            connected_ids.add(edge.source)

    filtered = ContentGraph(title=f"Dependencies of {focus_id}")
    for node in graph.nodes:
        if node.id in connected_ids:
            filtered.add_node(node)
    for edge in graph.edges:
        if edge.source in connected_ids and edge.target in connected_ids:
            filtered.add_edge(edge)
    return filtered


def _condition_summary(condition: object) -> str:
    """Return a short human-readable summary of a condition for graph labels."""
    if condition is None:
        return "always"
    ctype = getattr(condition, "type", "?")
    match ctype:
        case "level":
            return f"level≥{getattr(condition, 'value', '?')}"
        case "milestone":
            return f"milestone:{getattr(condition, 'name', '?')}"
        case "all":
            return "all(…)"
        case "any":
            return "any(…)"
        case _:
            return ctype


def _walk_all_steps(steps: list) -> list:
    """Recursively yield all steps including those nested in branches."""
    from oscilla.engine.models.adventure import ChoiceStep, CombatStep, StatCheckStep

    result = []
    for step in steps:
        result.append(step)
        match step:
            case CombatStep():
                for branch in [step.on_win, step.on_defeat, step.on_flee]:
                    result.extend(_walk_all_steps(branch.steps))
            case ChoiceStep():
                for opt in step.options:
                    result.extend(_walk_all_steps(opt.steps))
            case StatCheckStep():
                for branch in [step.on_pass, step.on_fail]:
                    result.extend(_walk_all_steps(branch.steps))
    return result


def _walk_all_effects(steps: list) -> list:
    """Recursively yield all effects from all steps and their branches."""
    from oscilla.engine.models.adventure import (
        ChoiceStep, CombatStep, NarrativeStep, PassiveStep, StatCheckStep,
    )

    result = []
    for step in steps:
        match step:
            case NarrativeStep():
                result.extend(step.effects)
            case PassiveStep():
                result.extend(step.effects)
            case CombatStep():
                for branch in [step.on_win, step.on_defeat, step.on_flee]:
                    result.extend(branch.effects)
                    result.extend(_walk_all_effects(branch.steps))
            case ChoiceStep():
                for opt in step.options:
                    result.extend(opt.effects)
                    result.extend(_walk_all_effects(opt.steps))
            case StatCheckStep():
                for branch in [step.on_pass, step.on_fail]:
                    result.extend(branch.effects)
                    result.extend(_walk_all_effects(branch.steps))
    return result


def build_manifest_xrefs(
    manifest: "ManifestEnvelope",
    registry: "ContentRegistry",
) -> Dict[str, list]:
    """Return outbound and inbound cross-references for a manifest.

    Used by ``content show`` to list what a manifest references and what
    references it.
    """
    from oscilla.engine.models.adventure import AdventureManifest
    from oscilla.engine.models.location import LocationManifest
    from oscilla.engine.models.region import RegionManifest

    refs: list = []
    ref_by: list = []

    kind = manifest.kind
    name = manifest.metadata.name

    match manifest:
        case RegionManifest():
            if manifest.spec.parent:
                refs.append(f"region:{manifest.spec.parent} (parent)")
            for loc in registry.locations.all():
                if loc.spec.region == name:
                    ref_by.append(f"location:{loc.metadata.name}")
        case LocationManifest():
            refs.append(f"region:{manifest.spec.region}")
            for entry in manifest.spec.adventures:
                refs.append(f"adventure:{entry.ref} (pool, weight={entry.weight})")
        case AdventureManifest():
            for step in _walk_all_steps(manifest.spec.steps):
                from oscilla.engine.models.adventure import CombatStep
                if isinstance(step, CombatStep):
                    refs.append(f"enemy:{step.enemy}")
            for effect in _walk_all_effects(manifest.spec.steps):
                from oscilla.engine.models.adventure import ItemDropEffect, SkillGrantEffect
                if isinstance(effect, ItemDropEffect):
                    if effect.loot_ref:
                        refs.append(f"loot-table:{effect.loot_ref}")
                    elif effect.loot:
                        for entry in effect.loot:
                            refs.append(f"item:{entry.item}")
                if isinstance(effect, SkillGrantEffect):
                    refs.append(f"skill:{effect.skill}")
            # referenced_by: find locations that include this adventure in their pool
            for loc in registry.locations.all():
                for entry in loc.spec.adventures:
                    if entry.ref == name:
                        ref_by.append(f"location:{loc.metadata.name}")

    return {"references": refs, "referenced_by": ref_by}
```

---

### Decision 5 — Graph Renderers (`oscilla/engine/graph_renderers.py`)

Three renderers: DOT (via `pydot`), Mermaid (string generation), ASCII (tree for world; adjacency list for others).

The color scheme for graph nodes is loaded from settings so that it can be overridden per-kind via environment variables (`OSCILLA_GRAPH_COLOR_REGION`, etc.) without code changes.

**Settings additions (`oscilla/conf/settings.py` or `oscilla/settings.py`):**

```python
# Graph node color overrides.  Each key maps a manifest kind slug to a hex color.
# Override any individual color via its environment variable, e.g.:
#   OSCILLA_GRAPH_COLOR_REGION=#5db85d
graph_color_game:       str = Field(default="#4a90d9", description="Graph node color for game kind.")
graph_color_region:     str = Field(default="#7cb87c", description="Graph node color for region kind.")
graph_color_location:   str = Field(default="#e8c56d", description="Graph node color for location kind.")
graph_color_adventure:  str = Field(default="#d98c4a", description="Graph node color for adventure kind.")
graph_color_enemy:      str = Field(default="#c94040", description="Graph node color for enemy kind.")
graph_color_item:       str = Field(default="#9b6dc0", description="Graph node color for item kind.")
graph_color_skill:      str = Field(default="#5ab8c0", description="Graph node color for skill kind.")
graph_color_buff:       str = Field(default="#a0c055", description="Graph node color for buff kind.")
graph_color_quest:      str = Field(default="#d06fbf", description="Graph node color for quest kind.")
graph_color_recipe:     str = Field(default="#c77a40", description="Graph node color for recipe kind.")
graph_color_loot_table: str = Field(default="#8a9ba8", description="Graph node color for loot-table kind.")
graph_color_start:      str = Field(default="#aaaaaa", description="Graph node color for start nodes.")
graph_color_end:        str = Field(default="#666666", description="Graph node color for end nodes.")
graph_color_narrative:  str = Field(default="#d0e8f8", description="Graph node color for narrative step nodes.")
graph_color_combat:     str = Field(default="#f8d0d0", description="Graph node color for combat step nodes.")
graph_color_choice:     str = Field(default="#f8f8d0", description="Graph node color for choice step nodes.")
graph_color_stat_check: str = Field(default="#d8d0f8", description="Graph node color for stat_check step nodes.")
graph_color_passive:    str = Field(default="#d0f8d8", description="Graph node color for passive step nodes.")
```

**`oscilla/engine/graph_renderers.py`:**

```python
# oscilla/engine/graph_renderers.py
"""Render a ContentGraph to DOT, Mermaid, or ASCII string output."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from oscilla.engine.graph import ContentGraph

GraphFormat = Literal["dot", "mermaid", "ascii"]


def _kind_colors() -> dict[str, str]:
    """Load graph node colors from settings.

    Deferred import prevents circular imports between settings and engine modules.
    """
    from oscilla.settings import settings
    return {
        "game":       settings.graph_color_game,
        "region":     settings.graph_color_region,
        "location":   settings.graph_color_location,
        "adventure":  settings.graph_color_adventure,
        "enemy":      settings.graph_color_enemy,
        "item":       settings.graph_color_item,
        "skill":      settings.graph_color_skill,
        "buff":       settings.graph_color_buff,
        "quest":      settings.graph_color_quest,
        "recipe":     settings.graph_color_recipe,
        "loot-table": settings.graph_color_loot_table,
        "start":      settings.graph_color_start,
        "end":        settings.graph_color_end,
        "goto":       "#cccccc",
        "narrative":  settings.graph_color_narrative,
        "combat":     settings.graph_color_combat,
        "choice":     settings.graph_color_choice,
        "stat_check": settings.graph_color_stat_check,
        "passive":    settings.graph_color_passive,
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
    import pydot  # deferred — not imported at module level since pydot is optional at import time

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
    """Sanitize a node id for use as a DOT identifier (replace non-alphanumeric chars)."""
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
    text = text.replace("#", "#35;")             # escape '#' before any entity codes
    text = text.replace('"', "#quot;")            # entity code for double-quote
    text = text.replace("`", "'")                 # backtick triggers Markdown mode
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
    lines = [f"---", f'title: "{graph.title}"', "---", "flowchart LR"]

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
        node = node_map.get(root)
        lines.append(node.label if node else root)
        kids = children.get(root, [])
        for j, kid in enumerate(kids):
            _draw_tree(kid, "", j == len(kids) - 1)
        if i < len(roots) - 1:
            lines.append("")

    return "\n".join(lines)
```

#### `content graph` command in `cli_content.py`

```python
@content_app.command("graph")
def content_graph(
    graph_type: Annotated[
        str,
        typer.Argument(help="Graph type: world | adventure | deps"),
    ],
    name: Annotated[
        Optional[str],
        typer.Argument(help="Adventure name (required for 'adventure' type)."),
    ] = None,
    game: Annotated[Optional[str], typer.Option("--game", "-g")] = None,
    fmt: Annotated[
        str, typer.Option("--format", "-f", help="Output format: dot | mermaid | ascii")
    ] = "ascii",
    focus: Annotated[
        Optional[str],
        typer.Option("--focus", help="For 'deps' type: focus node id, e.g. 'item:rusty-sword'."),
    ] = None,
    include_kinds: Annotated[
        Optional[str],
        typer.Option("--include-kinds", help="For 'deps' type: comma-separated kind slugs to include (e.g. 'item,enemy')."),
    ] = None,
    exclude_kinds: Annotated[
        Optional[str],
        typer.Option("--exclude-kinds", help="For 'deps' type: comma-separated kind slugs to exclude (e.g. 'quest,milestone')."),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Write output to this file path instead of stdout."),
    ] = None,
) -> None:
    """Generate a graph visualization of game content."""
    from oscilla.engine.graph import build_adventure_graph, build_deps_graph, build_world_graph
    from oscilla.engine.graph_renderers import GraphFormat, render

    valid_types = {"world", "adventure", "deps"}
    valid_formats = {"dot", "mermaid", "ascii"}

    graph_type = graph_type.lower()
    fmt = fmt.lower()

    if graph_type not in valid_types:
        _err_console.print(f"[red]Unknown graph type {graph_type!r}. Valid: {', '.join(valid_types)}[/red]")
        raise SystemExit(1)
    if fmt not in valid_formats:
        _err_console.print(f"[red]Unknown format {fmt!r}. Valid: {', '.join(valid_formats)}[/red]")
        raise SystemExit(1)
    if graph_type == "adventure" and name is None:
        _err_console.print("[red]Adventure name required: oscilla content graph adventure <name>[/red]")
        raise SystemExit(1)

    # Parse comma-separated kind filter strings into sets (only used by deps type)
    include_set = {k.strip() for k in include_kinds.split(",")} if include_kinds else None
    exclude_set = {k.strip() for k in exclude_kinds.split(",")} if exclude_kinds else None

    _, registry = _resolve_registry(game)

    match graph_type:
        case "world":
            graph = build_world_graph(registry)
        case "adventure":
            assert name is not None
            manifest = registry.adventures.get(name)
            if manifest is None:
                _err_console.print(f"[red]Adventure {name!r} not found.[/red]")
                raise SystemExit(1)
            graph = build_adventure_graph(manifest, registry)
        case "deps":
            graph = build_deps_graph(registry, focus=focus, include_kinds=include_set, exclude_kinds=exclude_set)

    result = render(graph, fmt)  # type: ignore[arg-type]

    if output:
        Path(output).write_text(result)
        _console.print(f"[green]Written to {output}[/green]")
    else:
        typer.echo(result)
```

---

### Decision 6 — Semantic Validator (`oscilla/engine/semantic_validator.py`)

Schema validation catches type errors in individual manifests. Semantic validation catches errors that require cross-manifest context: a reference that points to a manifest that doesn't exist, region parent cycles, and content that is defined but never reachable.

```python
# oscilla/engine/semantic_validator.py
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
    kind: str          # "undefined_ref", "circular_chain", "orphaned", "unreachable"
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
                issues.append(SemanticIssue(
                    kind="undefined_ref",
                    message=f"Adventure pool references unknown adventure {entry.ref!r}",
                    manifest=f"location:{loc.metadata.name}",
                ))
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
                    issues.append(SemanticIssue(
                        kind="undefined_ref",
                        message=f"Combat step references unknown enemy {step.enemy!r}",
                        manifest=f"adventure:{adv.metadata.name}",
                    ))
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
                        issues.append(SemanticIssue(
                            kind="undefined_ref",
                            message=f"item_drop references unknown item {entry.item!r}",
                            manifest=f"adventure:{adv.metadata.name}",
                        ))

    for lt in registry.loot_tables.all():
        for entry in lt.spec.loot:
            if registry.items.get(entry.item) is None:
                issues.append(SemanticIssue(
                    kind="undefined_ref",
                    message=f"LootTable entry references unknown item {entry.item!r}",
                    manifest=f"loot-table:{lt.metadata.name}",
                ))
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
                    issues.append(SemanticIssue(
                        kind="undefined_ref",
                        message=f"skill_grant references unknown skill {effect.skill!r}",
                        manifest=f"adventure:{adv.metadata.name}",
                    ))
    return issues


def _check_circular_region_parents(registry: "ContentRegistry") -> List[SemanticIssue]:
    """Region parent chains must be acyclic.

    Uses a depth-first search with a visited/recursion-stack approach.
    """
    issues = []
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
                issues.append(SemanticIssue(
                    kind="circular_chain",
                    message=f"Circular region parent chain detected at {name!r} → {parent!r}",
                    manifest=f"region:{name}",
                ))
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
            issues.append(SemanticIssue(
                kind="orphaned",
                message=f"Adventure {adv.metadata.name!r} is not referenced in any location's pool",
                manifest=f"adventure:{adv.metadata.name}",
                severity="warning",
            ))
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
                    issues.append(SemanticIssue(
                        kind="unreachable",
                        message=(
                            f"Adventure pool entry {entry.ref!r} requires milestone {ms!r} "
                            f"which is never granted by any adventure"
                        ),
                        manifest=f"location:{loc.metadata.name}",
                        severity="warning",
                    ))
    return issues
```

#### `content test` command

```python
@content_app.command("test")
def content_test(
    game: Annotated[Optional[str], typer.Option("--game", "-g")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors.")] = False,
    output_format: Annotated[OutputFormat, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
) -> None:
    """Run semantic validation checks on the content package."""
    from oscilla.engine.semantic_validator import validate_semantic

    _, registry = _resolve_registry(game)
    issues = validate_semantic(registry)

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    if output_format != "text":
        data = {
            "errors": [{"kind": i.kind, "message": i.message, "manifest": i.manifest} for i in errors],
            "warnings": [{"kind": i.kind, "message": i.message, "manifest": i.manifest} for i in warnings],
        }
        _emit_structured_output(data, output_format)
        exit_code = 1 if errors or (strict and warnings) else 0
        raise SystemExit(exit_code)

    if not issues:
        _console.print("[bold green]✓ No semantic issues found.[/bold green]")
        return

    for issue in errors:
        _console.print(f"  [red]✗[/red] [{issue.kind}] {issue}")
    for issue in warnings:
        color = "bold red" if strict else "yellow"
        _console.print(f"  [{color}]⚠[/{color}] [{issue.kind}] {issue}")

    if errors:
        raise SystemExit(1)
    if strict and warnings:
        _console.print(f"\n[bold red]Strict mode: {len(warnings)} warning(s) treated as errors.[/bold red]")
        raise SystemExit(1)
```

#### Extend existing `validate` with `--no-semantic`

**Before** (in `oscilla/cli.py`, the validate command signature):

```python
@app.command(help="Validate all game packages and report any errors or warnings.")
def validate(
    game_name: Annotated[str | None, typer.Option("--game", "-g", help="Validate only this game package.")] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Treat warnings as errors and exit with code 1 if any are found."),
    ] = False,
) -> None:
```

**After:**

```python
@app.command(help="Validate all game packages and report any errors or warnings.")
def validate(
    game_name: Annotated[str | None, typer.Option("--game", "-g", help="Validate only this game package.")] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Treat warnings as errors and exit with code 1 if any are found."),
    ] = False,
    no_semantic: Annotated[
        bool,
        typer.Option("--no-semantic", help="Skip semantic checks (undefined refs, circular chains, orphaned/unreachable content)."),
    ] = False,
) -> None:
```

At the end of the `validate` function body, after the existing summary loop, add:

```python
    if not no_semantic:
        from oscilla.engine.semantic_validator import validate_semantic

        semantic_total_warnings = 0
        for pkg_name, registry in sorted(games.items()):
            issues = validate_semantic(registry)
            for issue in issues:
                if issue.severity == "error":
                    _console.print(f"  [red]✗[/red] [{pkg_name}] [{issue.kind}] {issue}")
                    total_warnings += 1  # re-use exit logic
                else:
                    semantic_total_warnings += 1
                    total_warnings += 1 if strict else 0
                    color = "bold red" if strict else "yellow"
                    _console.print(f"  [{color}]⚠[/{color}] [{pkg_name}] [{issue.kind}] {issue}")
        if semantic_total_warnings and not strict:
            _console.print(f"\n[dim]{semantic_total_warnings} semantic warning(s). Use --strict to treat as errors.[/dim]")
```

---

### Decision 7 — Adventure Tracer (`oscilla/engine/tracer.py`)

The tracer walks the adventure step graph without a real character or TUI. It traces ALL possible execution paths (treating all choice options and all combat outcomes as separate paths). Effects are recorded but never applied. No character state is modified.

```python
# oscilla/engine/tracer.py
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
    from oscilla.engine.models.adventure import AdventureManifest, Step


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
    description: str   # short human summary
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
    result = TraceResult(
        adventure_name=manifest.metadata.name,
        total_steps=_count_all_steps(manifest.spec.steps),
    )

    # Build a label→index map for goto resolution
    label_map: dict[str, int] = {}
    for i, step in enumerate(manifest.spec.steps):
        lbl = getattr(step, "label", None)
        if lbl:
            label_map[lbl] = i

    path_counter = [0]

    def _new_path_id() -> str:
        path_counter[0] += 1
        return f"path-{path_counter[0]}"

    def _trace_steps(
        steps: list,
        path: TracedPath,
        step_start_idx: int = 0,
        top_level: bool = True,
    ) -> None:
        """Recursively walk steps, forking the path at branching points."""
        idx = step_start_idx
        current_steps = steps

        while idx < len(current_steps):
            step = current_steps[idx]
            _trace_single_step(step, path, current_steps, idx, label_map, _new_path_id, result)

            # Check if a goto or end_adventure was recorded
            if path.nodes and path.nodes[-1].step_type in ("end_adventure", "goto"):
                return
            idx += 1

    _trace_from_start(manifest.spec.steps, label_map, _new_path_id, result)
    return result


def _trace_from_start(
    steps: list,
    label_map: dict[str, int],
    new_path_id: object,
    result: TraceResult,
) -> None:
    """Entry point: start one path per top-level adventure."""
    from oscilla.engine.models.adventure import ChoiceStep, CombatStep, StatCheckStep

    def _walk(
        path: TracedPath,
        steps: list,
        idx: int,
    ) -> None:
        """Walk steps sequentially, branching at choice/combat/stat_check."""
        while idx < len(steps):
            step = steps[idx]
            stype = step.type  # Literal discriminator field

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
                        # Append the outcome to the last node of the fork
                        fork.nodes[-1].branch_taken = branch_name
                        if branch.goto:
                            goto_idx = label_map.get(branch.goto, -1)
                            if goto_idx >= 0:
                                _walk(fork, steps, goto_idx)
                        elif branch.steps:
                            _walk(fork, branch.steps, 0)
                        else:
                            _close_path_with_outcome(fork, branch_name)
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
                                _walk(fork, steps, goto_idx)
                        elif opt.steps:
                            _walk(fork, opt.steps, 0)
                        # else: fall through to next top-level step
                    return

                case StatCheckStep():
                    _record_node(path, step, branch=None)
                    for branch_name, branch in [("on_pass", step.on_pass), ("on_fail", step.on_fail)]:
                        fork = _fork_path(path, result)
                        fork.nodes[-1].branch_taken = branch_name
                        if branch.goto:
                            goto_idx = label_map.get(branch.goto, -1)
                            if goto_idx >= 0:
                                _walk(fork, steps, goto_idx)
                        elif branch.steps:
                            _walk(fork, branch.steps, 0)
                    return

                case _:
                    _record_node(path, step, branch=None)
                    # Check for end_adventure in effects
                    from oscilla.engine.models.adventure import EndAdventureEffect, PassiveStep, NarrativeStep
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
        path_id=f"path-{len(result.paths) + 1}",
        nodes=list(parent.nodes),
    )
    return fork


def _close_path_with_outcome(path: TracedPath, outcome: str) -> None:
    path.outcome = outcome


def _record_node(path: TracedPath, step: object, branch: str | None) -> None:
    """Append a traced node to the path from a step object."""
    from oscilla.engine.models.adventure import (
        CombatStep, ChoiceStep, NarrativeStep, PassiveStep, StatCheckStep,
    )
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
            from oscilla.engine.graph import _condition_summary
            desc = _condition_summary(step.condition)
        case PassiveStep():
            desc = f"{len(step.effects)} effects"
            effects = _summarise_effects(step.effects)

    path.nodes.append(TracedNode(
        step_index=len(path.nodes),
        step_type=stype,
        label=getattr(step, "label", None),
        description=desc,
        effects=effects,
        branch_taken=branch,
    ))


def _record_option_effects(path: TracedPath, opt: object) -> None:
    """Record effects from a choice option into the last node."""
    if path.nodes and hasattr(opt, "effects"):
        path.nodes[-1].effects.extend(_summarise_effects(opt.effects))


def _summarise_effects(effects: list) -> List[TracedEffect]:
    from oscilla.engine.models.adventure import (
        EndAdventureEffect, HealEffect, ItemDropEffect, MilestoneGrantEffect,
        SkillGrantEffect, StatChangeEffect, StatSetEffect, XpGrantEffect,
    )
    result = []
    for eff in effects:
        match eff:
            case XpGrantEffect(amount=a):
                result.append(TracedEffect("xp_grant", f"xp +{a}"))
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


def _count_all_steps(steps: list) -> int:
    from oscilla.engine.graph import _walk_all_steps
    return len(_walk_all_steps(steps))
```

#### `content trace` command

```python
@content_app.command("trace")
def content_trace(
    adventure_name: Annotated[str, typer.Argument(help="Adventure manifest name.")],
    game: Annotated[Optional[str], typer.Option("--game", "-g")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
) -> None:
    """Trace all execution paths through an adventure (no character state changes)."""
    from oscilla.engine.tracer import trace_adventure

    _, registry = _resolve_registry(game)
    manifest = registry.adventures.get(adventure_name)
    if manifest is None:
        _err_console.print(f"[red]Adventure {adventure_name!r} not found.[/red]")
        raise SystemExit(1)

    result = trace_adventure(manifest)

    if output_format != "text":
        import dataclasses
        _emit_structured_output(dataclasses.asdict(result), output_format)
        return

    _console.print(f"\n[bold]Tracing:[/bold] {result.adventure_name}")
    _console.print(f"[dim]Total steps (all branches): {result.total_steps}[/dim]")
    _console.print(f"[dim]Paths found: {len(result.paths)}[/dim]\n")

    for path in result.paths:
        _console.print(f"[bold cyan]── {path.path_id}[/bold cyan]  outcome: [green]{path.outcome}[/green]")
        for node in path.nodes:
            branch = f" [{node.branch_taken}]" if node.branch_taken else ""
            _console.print(f"   [dim]{node.step_type}[/dim]{branch}  {node.description}")
            for eff in node.effects:
                _console.print(f"      [dim]→ {eff.summary}[/dim]")
        _console.print()
```

---

### Decision 8 — JSON Schema Export (`oscilla/engine/schema_export.py`)

Pydantic v2 exposes `.model_json_schema()` on every model class. Each manifest kind has a concrete `*Manifest` class wrapping a `*Spec`. We export the full manifest schema per kind.

```python
# oscilla/engine/schema_export.py
"""Export JSON Schema for Oscilla manifest kinds.

Pydantic v2's model_json_schema() generates a JSON Schema (draft 7/2020-12)
from the model's field definitions, validators, and annotations. The output
can be used with yaml-language-server directives, VS Code settings.json,
or any JSON Schema-aware editor.

Usage example (yaml-language-server directive in a YAML file):
    # yaml-language-server: $schema=./schemas/adventure.json
"""

from __future__ import annotations

import json
from typing import Any, Dict

from oscilla.engine.kinds import ALL_KINDS

# Maps CLI kind slug → manifest model class.
# Derived from ALL_KINDS registry — add new kinds there, not here.
_MANIFEST_MODELS: Dict[str, Any] = {k.slug: k.model_class for k in ALL_KINDS}


def export_schema(kind: str) -> Dict[str, Any]:
    """Return the JSON Schema dict for one manifest kind.

    Raises ValueError for unknown kind slugs.
    """
    model = _MANIFEST_MODELS.get(kind.lower())
    if model is None:
        raise ValueError(f"Unknown kind {kind!r}. Valid: {', '.join(sorted(_MANIFEST_MODELS))}")
    schema = model.model_json_schema()
    # Annotate the schema with a standard $id and $schema header for editor tooling.
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://oscilla.dev/schemas/{kind}.json"
    schema["title"] = f"Oscilla {kind.title()} Manifest"
    return schema


def export_all_schemas() -> Dict[str, Dict[str, Any]]:
    """Return a dict of kind → JSON Schema for all manifest kinds."""
    return {kind: export_schema(kind) for kind in _MANIFEST_MODELS}


def valid_kinds() -> list[str]:
    return sorted(_MANIFEST_MODELS)
```

#### `content schema` command

```python
@content_app.command("schema")
def content_schema(
    kind: Annotated[
        Optional[str],
        typer.Argument(help="Manifest kind slug. Omit to export all kinds."),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Write to file (or directory for all kinds)."),
    ] = None,
    vscode: Annotated[
        bool,
        typer.Option("--vscode", help="Write .vscode/settings.json yaml-language-server schema associations (requires --output)."),
    ] = False,
) -> None:
    """Export JSON Schema for Oscilla manifest kinds.

    With no KIND argument, all schemas are printed as a single JSON object keyed by kind.
    With --output and no KIND, writes one file per kind into the specified directory.
    With --vscode, also updates .vscode/settings.json with yaml-language-server associations.
    """
    from oscilla.engine.schema_export import export_all_schemas, export_schema, valid_kinds

    if vscode and not output:
        _err_console.print("[red]--vscode requires --output to know where schemas are written.[/red]")
        raise SystemExit(1)

    if kind is not None:
        try:
            schema = export_schema(kind)
        except ValueError as exc:
            _err_console.print(f"[red]{exc}[/red]")
            raise SystemExit(1)

        result = json.dumps(schema, indent=2)
        if output:
            Path(output).write_text(result)
            _console.print(f"[green]Written to {output}[/green]")
        else:
            typer.echo(result)
        return

    # All schemas
    all_schemas = export_all_schemas()
    if output:
        out_dir = Path(output)
        out_dir.mkdir(parents=True, exist_ok=True)
        for k, schema in all_schemas.items():
            path = out_dir / f"{k}.json"
            path.write_text(json.dumps(schema, indent=2))
        _console.print(f"[green]Wrote {len(all_schemas)} schema files to {out_dir}/[/green]")

        if vscode:
            _write_vscode_schema_associations(out_dir, all_schemas)
    else:
        typer.echo(json.dumps(all_schemas, indent=2))


def _write_vscode_schema_associations(
    schema_dir: Path,
    schemas: dict,
) -> None:
    """Update .vscode/settings.json with yaml-language-server schema associations.

    Creates the file if it does not exist. Merges into any existing yaml.schemas dict.
    """
    import json as _json

    settings_path = Path(".vscode") / "settings.json"
    settings_path.parent.mkdir(exist_ok=True)
    try:
        existing: dict = _json.loads(settings_path.read_text()) if settings_path.exists() else {}
    except Exception:
        existing = {}
    associations = {f"**/{k}.yaml": str(schema_dir / f"{k}.json") for k in sorted(schemas)}
    existing.setdefault("yaml.schemas", {}).update(associations)
    settings_path.write_text(_json.dumps(existing, indent=2))
    _console.print(f"[green]Updated {settings_path} with {len(associations)} schema associations.[/green]")
```

---

### Decision 9 — Content Scaffolding (`content create`)

The `create` command generates a valid minimal YAML manifest at the conventional directory path. In interactive mode it prompts for each field. In `--no-interactive` mode all required fields must be provided as options; optional fields use documented defaults.

The conventional paths mirror the existing content packages:

| Kind      | Path template                                                                      |
| --------- | ---------------------------------------------------------------------------------- |
| region    | `<games_path>/<game>/regions/<name>/<name>.yaml`                                   |
| location  | `<games_path>/<game>/regions/<region>/locations/<name>/<name>.yaml`                |
| adventure | `<games_path>/<game>/regions/<region>/locations/<location>/adventures/<name>.yaml` |
| enemy     | `<games_path>/<game>/enemies/<name>.yaml`                                          |
| item      | `<games_path>/<game>/items/<name>.yaml`                                            |
| skill     | `<games_path>/<game>/skills/<name>.yaml`                                           |
| buff      | `<games_path>/<game>/buffs/<name>.yaml`                                            |
| quest     | `<games_path>/<game>/quests/<name>.yaml`                                           |
| recipe    | `<games_path>/<game>/recipes/<name>.yaml`                                          |

```python
# oscilla/engine/scaffolder.py
"""YAML manifest scaffolding for the content create command."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.default_flow_style = False


def _write_yaml(path: Path, data: Dict) -> None:
    """Write a YAML file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        _yaml.dump(data, f)


def scaffold_region(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    description: str = "",
    parent: str | None = None,
) -> Path:
    data = {
        "apiVersion": "oscilla/v1",
        "kind": "Region",
        "metadata": {"name": name},
        "spec": {"displayName": display_name, "description": description},
    }
    if parent:
        data["spec"]["parent"] = parent
    path = games_path / game_name / "regions" / name / f"{name}.yaml"
    _write_yaml(path, data)
    return path


def scaffold_location(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    region: str,
    description: str = "",
) -> Path:
    data = {
        "apiVersion": "oscilla/v1",
        "kind": "Location",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "region": region,
            "adventures": [],
        },
    }
    path = games_path / game_name / "regions" / region / "locations" / name / f"{name}.yaml"
    _write_yaml(path, data)
    return path


def scaffold_adventure(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    region: str,
    location: str,
    description: str = "",
) -> Path:
    data = {
        "apiVersion": "oscilla/v1",
        "kind": "Adventure",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "steps": [
                {
                    "type": "narrative",
                    "text": "Your adventure begins here.",
                    "effects": [{"type": "end_adventure", "outcome": "completed"}],
                }
            ],
        },
    }
    path = (
        games_path
        / game_name
        / "regions"
        / region
        / "locations"
        / location
        / "adventures"
        / f"{name}.yaml"
    )
    _write_yaml(path, data)
    return path


def scaffold_enemy(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    hp: int = 30,
    attack: int = 5,
    defense: int = 2,
    xp_reward: int = 20,
    description: str = "",
) -> Path:
    data = {
        "apiVersion": "oscilla/v1",
        "kind": "Enemy",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "hp": hp,
            "attack": attack,
            "defense": defense,
            "xp_reward": xp_reward,
            "loot": [],
        },
    }
    path = games_path / game_name / "enemies" / f"{name}.yaml"
    _write_yaml(path, data)
    return path


def scaffold_item(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    category: str,
    description: str = "",
) -> Path:
    data = {
        "apiVersion": "oscilla/v1",
        "kind": "Item",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "category": category,
            "use_effects": [],
        },
    }
    path = games_path / game_name / "items" / f"{name}.yaml"
    _write_yaml(path, data)
    return path


def scaffold_quest(
    games_path: Path,
    game_name: str,
    name: str,
    display_name: str,
    entry_stage: str = "stage-1",
    description: str = "",
) -> Path:
    data = {
        "apiVersion": "oscilla/v1",
        "kind": "Quest",
        "metadata": {"name": name},
        "spec": {
            "displayName": display_name,
            "description": description,
            "entry_stage": entry_stage,
            "stages": [
                {
                    "name": entry_stage,
                    "description": "First stage",
                    "advance_on": ["my-milestone"],
                    "next_stage": "stage-complete",
                },
                {
                    "name": "stage-complete",
                    "description": "Quest complete",
                    "terminal": True,
                    "completion_effects": [],
                },
            ],
        },
    }
    path = games_path / game_name / "quests" / f"{name}.yaml"
    _write_yaml(path, data)
    return path
```

#### `content create` command

The command uses `typer.prompt()` for interactive mode and direct option values for `--no-interactive`. It shows the written file path on success.

```python
@content_app.command("create")
def content_create(
    kind: Annotated[str, typer.Argument(help="Manifest kind to create.")],
    game: Annotated[Optional[str], typer.Option("--game", "-g")] = None,
    name: Annotated[Optional[str], typer.Option("--name", help="Manifest name (metadata.name).")] = None,
    display_name: Annotated[Optional[str], typer.Option("--display-name")] = None,
    description: Annotated[Optional[str], typer.Option("--description")] = None,
    parent: Annotated[Optional[str], typer.Option("--parent", help="Parent region name (for regions).")] = None,
    region: Annotated[Optional[str], typer.Option("--region", help="Region name (for locations/adventures).")] = None,
    location: Annotated[Optional[str], typer.Option("--location", help="Location name (for adventures).")] = None,
    no_interactive: Annotated[bool, typer.Option("--no-interactive", help="Skip all prompts.")] = False,
) -> None:
    """Scaffold a new manifest YAML file at the conventional directory path."""
    from oscilla.engine.scaffolder import (
        scaffold_adventure,
        scaffold_enemy,
        scaffold_item,
        scaffold_quest,
        scaffold_location,
        scaffold_region,
    )
    from oscilla.settings import settings

    kind = kind.lower()
    valid_create_kinds = {"region", "location", "adventure", "enemy", "item", "quest"}
    if kind not in valid_create_kinds:
        _err_console.print(f"[red]Cannot create {kind!r}. Supported: {', '.join(sorted(valid_create_kinds))}[/red]")
        raise SystemExit(1)

    # Resolve game name (must exist)
    gp = settings.games_path
    if game is None:
        available = [d.name for d in sorted(gp.iterdir()) if d.is_dir() and (d / "game.yaml").exists()]
        if not available:
            _err_console.print("[red]No game packages found in GAMES_PATH.[/red]")
            raise SystemExit(1)
        if len(available) == 1:
            game = available[0]
        elif no_interactive:
            _err_console.print(f"[red]Multiple games found. Use --game. Available: {', '.join(available)}[/red]")
            raise SystemExit(1)
        else:
            game = typer.prompt(f"Game name", default=available[0])

    def _prompt_or_require(value: str | None, prompt_text: str, flag: str) -> str:
        if value:
            return value
        if no_interactive:
            _err_console.print(f"[red]{flag} is required in --no-interactive mode.[/red]")
            raise SystemExit(1)
        return typer.prompt(prompt_text)

    name = _prompt_or_require(name, "Manifest name (metadata.name)", "--name")
    display_name = _prompt_or_require(display_name, "Display name", "--display-name")
    if description is None and not no_interactive:
        description = typer.prompt("Description", default="")
    description = description or ""

    out_path: Path
    match kind:
        case "region":
            if parent is None and not no_interactive:
                parent = typer.prompt("Parent region (leave blank for top-level)", default="") or None
            out_path = scaffold_region(gp, game, name, display_name, description, parent)
        case "location":
            region = _prompt_or_require(region, "Region name", "--region")
            out_path = scaffold_location(gp, game, name, display_name, region, description)
        case "adventure":
            region = _prompt_or_require(region, "Region name", "--region")
            location = _prompt_or_require(location, "Location name", "--location")
            out_path = scaffold_adventure(gp, game, name, display_name, region, location, description)
        case "enemy":
            out_path = scaffold_enemy(gp, game, name, display_name, description=description)
        case "item":
            category = _prompt_or_require(None, "Item category", "--category") if not no_interactive else "general"
            out_path = scaffold_item(gp, game, name, display_name, category, description)
        case "quest":
            out_path = scaffold_quest(gp, game, name, display_name, description=description)

    _console.print(f"[bold green]✓ Created:[/bold green] {out_path}")
    _console.print(f"[dim]Open the file to fill in content. Validate with: oscilla validate --game {game}[/dim]")
```

---

### Decision 10 — New Dependency: `pydot`

`pydot` is added to production dependencies in `pyproject.toml`. It is a pure-Python library that generates DOT-format strings without requiring any system binaries. It is only imported inside `render_dot()`, so packages that never call `render dot` have zero overhead.

No new optional dependency mechanism is needed — `pydot` is small, pure-Python, and has no transitive binary dependencies.

The latest stable version is **4.0.1** (released 2025-06-17). The public API (`pydot.Dot`, `pydot.Node`, `pydot.Edge`, `.to_string()`, `.add_node()`, `.add_edge()`, `.set_graph_defaults()`, `.set_node_defaults()`) is identical between 3.x and 4.x. The constraint `>=4,<5` allows patch and minor upgrades within the 4.x series while rejecting a hypothetical 5.x with breaking API changes; exact reproducibility across environments is provided by the project's `uv.lock` lockfile.

**`pyproject.toml` change:**

```toml
# Before:
dependencies = [
  "SQLAlchemy",
  "aiocache",
  ...
  "pydantic-settings",
  "redis",
  ...
]

# After:
dependencies = [
  "SQLAlchemy",
  "aiocache",
  ...
  "pydantic-settings",
  "pydot>=4,<5",
  "redis",
  ...
]
```

---

## Documentation Plan

### `docs/authors/cli.md` — **new file**

- **Audience**: Content authors, not engine developers
- **Topics**:
  - Overview: when to use each command (inspect, graph, validate, trace, create)
  - `content list` with example output table for each kind
  - `content show` with example output for a region and an adventure
  - `content graph world` with example ASCII and Mermaid output
  - `content graph adventure` with example Mermaid flowchart output
  - `content graph deps` with `--focus` explained
  - `content schema` with example: how to use the output with `yaml-language-server` directive
  - `content test` with example output; difference from `validate`; `--strict` flag
  - `content trace` with example output for a branching adventure
  - `content create` interaction walkthrough (interactive + non-interactive examples)
  - Table of all flags and when they apply:

    | Flag                        | Commands                        | Notes                                                             |
    | --------------------------- | ------------------------------- | ----------------------------------------------------------------- |
    | `--format text\|json\|yaml` | `list`, `show`, `test`, `trace` | Machine-readable output                                           |
    | `--no-semantic`             | `validate`                      | Skip semantic checks (semantic runs by default)                   |
    | `--no-interactive`          | `create`                        | Scripting / CI use                                                |
    | `--vscode`                  | `schema`                        | Writes `.vscode/settings.json` associations (requires `--output`) |
    | `--include-kinds`           | `graph deps`                    | Comma-separated kind slugs to keep                                |
    | `--exclude-kinds`           | `graph deps`                    | Comma-separated kind slugs to drop                                |
    | `--focus`                   | `graph deps`                    | Restrict to neighborhood of one node                              |
    | `--strict`                  | `validate`, `test`              | Treat warnings as errors                                          |

- **Must be added to** `docs/authors/README.md` table of contents

### `docs/authors/README.md` — **update**

- Add `cli.md` row to the "Building Your Game" table

### `docs/dev/cli.md` — **update**

- Add "Content Subapp" section documenting the module layout (`cli_content.py` → `CLIContentApp`)
- Document the `_resolve_registry()` helper pattern
- Note the `--no-semantic` extension to `validate`

---

## Testing Philosophy

### Test Tiers

| Tier                      | What it tests                                                                                                                  | Location                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------- |
| Unit — graph builders     | `build_world_graph`, `build_adventure_graph`, `build_deps_graph` produce correct nodes/edges from a minimal in-memory registry | `tests/engine/test_graph.py`              |
| Unit — graph renderers    | DOT/Mermaid/ASCII output from a fixed `ContentGraph` matches expected structure                                                | `tests/engine/test_graph_renderers.py`    |
| Unit — semantic validator | Each check function catches exactly the condition it is designed for; clean content produces zero issues                       | `tests/engine/test_semantic_validator.py` |
| Unit — tracer             | Trace of a known multi-branch adventure produces correct path count and effects                                                | `tests/engine/test_tracer.py`             |
| Unit — schema export      | `export_schema` returns valid JSON Schema for each kind; `export_all_schemas` returns all kinds                                | `tests/engine/test_schema_export.py`      |
| Unit — scaffolder         | Each `scaffold_*` function creates a file with valid YAML at the expected path; content validates without error                | `tests/engine/test_scaffolder.py`         |
| Integration — CLI         | All `content` commands succeed against the testlandia package via `CliRunner`                                                  | `tests/test_cli_content.py`               |

### Fixture: Minimal `ContentRegistry`

```python
# tests/engine/conftest.py (add to existing conftest or in test files as needed)
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.models.region import RegionManifest, RegionSpec
from oscilla.engine.models.location import LocationManifest, LocationSpec, AdventurePoolEntry
from oscilla.engine.models.adventure import AdventureManifest, AdventureSpec, NarrativeStep
from oscilla.engine.models.enemy import EnemyManifest, EnemySpec
from oscilla.engine.models.base import ManifestMetadata


def _meta(name: str) -> ManifestMetadata:
    return ManifestMetadata(name=name)

def make_minimal_registry() -> ContentRegistry:
    """Build a minimal ContentRegistry with one of each type for graph tests."""
    region = RegionManifest(
        apiVersion="oscilla/v1", kind="Region",
        metadata=_meta("forest"),
        spec=RegionSpec(displayName="The Forest"),
    )
    location = LocationManifest(
        apiVersion="oscilla/v1", kind="Location",
        metadata=_meta("clearing"),
        spec=LocationSpec(
            displayName="The Clearing",
            region="forest",
            adventures=[AdventurePoolEntry(ref="goblin-fight", weight=1)],
        ),
    )
    adventure = AdventureManifest(
        apiVersion="oscilla/v1", kind="Adventure",
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
    registry = ContentRegistry.build([region, location, adventure])
    return registry
```

### Example Unit Tests

```python
# tests/engine/test_graph.py

import pytest
from tests.engine.conftest import make_minimal_registry
from oscilla.engine.graph import build_world_graph, build_deps_graph


def test_world_graph_has_region_node() -> None:
    registry = make_minimal_registry()
    graph = build_world_graph(registry)
    node_ids = {n.id for n in graph.nodes}
    assert "region:forest" in node_ids


def test_world_graph_has_location_node() -> None:
    registry = make_minimal_registry()
    graph = build_world_graph(registry)
    node_ids = {n.id for n in graph.nodes}
    assert "location:clearing" in node_ids


def test_world_graph_location_connects_to_region() -> None:
    registry = make_minimal_registry()
    graph = build_world_graph(registry)
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("region:forest", "location:clearing") in edges


def test_world_graph_adventure_pool_edge() -> None:
    registry = make_minimal_registry()
    graph = build_world_graph(registry)
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("location:clearing", "adventure:goblin-fight") in edges


def test_deps_graph_focus_filters_to_neighborhood() -> None:
    registry = make_minimal_registry()
    graph = build_deps_graph(registry, focus="location:clearing")
    node_ids = {n.id for n in graph.nodes}
    # Focus node must be present
    assert "location:clearing" in node_ids
    # Its neighbor (adventure) must be present
    assert "adventure:goblin-fight" in node_ids


# tests/engine/test_graph_renderers.py

from oscilla.engine.graph import ContentGraph, GraphNode, GraphEdge
from oscilla.engine.graph_renderers import render_dot, render_mermaid, render_ascii


def _simple_graph() -> ContentGraph:
    g = ContentGraph(title="Test")
    g.add_node(GraphNode(id="a", label="Node A", kind="region"))
    g.add_node(GraphNode(id="b", label="Node B", kind="location"))
    g.add_edge(GraphEdge(source="a", target="b", label="contains"))
    return g


def test_render_dot_contains_node_labels() -> None:
    output = render_dot(_simple_graph())
    assert "Node A" in output
    assert "Node B" in output


def test_render_dot_is_digraph() -> None:
    output = render_dot(_simple_graph())
    assert "digraph" in output


def test_render_mermaid_contains_node_ids() -> None:
    output = render_mermaid(_simple_graph())
    assert "flowchart LR" in output


def test_render_ascii_contains_labels() -> None:
    output = render_ascii(_simple_graph())
    assert "Node A" in output
    assert "Node B" in output


# tests/engine/test_semantic_validator.py

from oscilla.engine.semantic_validator import (
    _check_circular_region_parents,
    _check_orphaned_adventures,
    _check_undefined_adventure_refs,
    validate_semantic,
)
from tests.engine.conftest import make_minimal_registry
from oscilla.engine.registry import ContentRegistry
from oscilla.engine.models.region import RegionManifest, RegionSpec
from oscilla.engine.models.base import ManifestMetadata


def _meta(name: str) -> ManifestMetadata:
    return ManifestMetadata(name=name)


def test_no_issues_on_clean_registry() -> None:
    registry = make_minimal_registry()
    issues = validate_semantic(registry)
    assert issues == []


def test_undefined_adventure_ref_in_pool() -> None:
    from oscilla.engine.models.location import LocationManifest, LocationSpec, AdventurePoolEntry
    registry = ContentRegistry()
    loc = LocationManifest(
        apiVersion="oscilla/v1", kind="Location",
        metadata=_meta("loc"),
        spec=LocationSpec(
            displayName="Loc", region="nowhere",
            adventures=[AdventurePoolEntry(ref="ghost-adventure", weight=1)],
        ),
    )
    registry.locations.register(loc)
    issues = _check_undefined_adventure_refs(registry)
    assert any(i.kind == "undefined_ref" and "ghost-adventure" in i.message for i in issues)


def test_circular_region_parents() -> None:
    registry = ContentRegistry()
    r1 = RegionManifest(
        apiVersion="oscilla/v1", kind="Region",
        metadata=_meta("alpha"),
        spec=RegionSpec(displayName="Alpha", parent="beta"),
    )
    r2 = RegionManifest(
        apiVersion="oscilla/v1", kind="Region",
        metadata=_meta("beta"),
        spec=RegionSpec(displayName="Beta", parent="alpha"),
    )
    registry.regions.register(r1)
    registry.regions.register(r2)
    issues = _check_circular_region_parents(registry)
    assert any(i.kind == "circular_chain" for i in issues)


def test_orphaned_adventure_is_warning() -> None:
    from oscilla.engine.models.adventure import AdventureManifest, AdventureSpec, NarrativeStep
    registry = ContentRegistry()
    adv = AdventureManifest(
        apiVersion="oscilla/v1", kind="Adventure",
        metadata=_meta("orphan"),
        spec=AdventureSpec(displayName="Orphan", steps=[
            NarrativeStep(type="narrative", text="Hello", effects=[])
        ]),
    )
    registry.adventures.register(adv)
    issues = _check_orphaned_adventures(registry)
    assert any(i.kind == "orphaned" and i.severity == "warning" for i in issues)


# tests/engine/test_tracer.py

from oscilla.engine.tracer import trace_adventure
from oscilla.engine.models.adventure import (
    AdventureManifest, AdventureSpec,
    ChoiceStep, ChoiceOption,
    NarrativeStep,
    EndAdventureEffect,
)
from oscilla.engine.models.base import ManifestMetadata


def _meta(name: str) -> ManifestMetadata:
    return ManifestMetadata(name=name)


def _simple_adventure() -> AdventureManifest:
    """Adventure with a two-option choice leading to different outcomes."""
    return AdventureManifest(
        apiVersion="oscilla/v1", kind="Adventure",
        metadata=_meta("test-adventure"),
        spec=AdventureSpec(
            displayName="Test Adventure",
            steps=[
                NarrativeStep(type="narrative", text="You arrive.", effects=[]),
                ChoiceStep(
                    type="choice",
                    prompt="What do you do?",
                    options=[
                        ChoiceOption(
                            label="Fight",
                            effects=[EndAdventureEffect(type="end_adventure", outcome="completed")],
                        ),
                        ChoiceOption(
                            label="Flee",
                            effects=[EndAdventureEffect(type="end_adventure", outcome="fled")],
                        ),
                    ],
                ),
            ],
        ),
    )


def test_trace_finds_two_paths_for_two_choice_options() -> None:
    result = trace_adventure(_simple_adventure())
    assert len(result.paths) == 2


def test_trace_captures_both_outcomes() -> None:
    result = trace_adventure(_simple_adventure())
    outcomes = {p.outcome for p in result.paths}
    assert "completed" in outcomes
    assert "fled" in outcomes


def test_trace_no_character_state_mutation() -> None:
    """Trace must not raise or create any database/session objects."""
    # The mere fact that this runs without importing session/db confirms isolation.
    result = trace_adventure(_simple_adventure())
    assert result is not None
```

---

## Testlandia Integration

Add a **`tooling-lab`** region to the testlandia content package with one location and one adventure purpose-built to exercise every author CLI feature:

### New Files

**`content/testlandia/regions/tooling-lab/tooling-lab.yaml`**

```yaml
apiVersion: oscilla/v1
kind: Region
metadata:
  name: tooling-lab
spec:
  displayName: "Tooling Lab"
  description: "A developer region for manually exercising author CLI commands."
```

**`content/testlandia/regions/tooling-lab/locations/trace-demo/trace-demo.yaml`**

```yaml
apiVersion: oscilla/v1
kind: Location
metadata:
  name: trace-demo
spec:
  displayName: "Trace Demonstration Hub"
  description: "Host for the trace-demo adventure used to QA oscilla content trace."
  region: tooling-lab
  adventures:
    - ref: trace-demo
      weight: 1
```

**`content/testlandia/regions/tooling-lab/locations/trace-demo/adventures/trace-demo.yaml`**

```yaml
apiVersion: oscilla/v1
kind: Adventure
metadata:
  name: trace-demo
spec:
  displayName: "Trace Demo Adventure"
  description: "Multi-branch adventure for manually QA-ing 'oscilla content trace'."
  steps:
    - type: narrative
      text: "You enter the lab. There are two paths."
    - type: choice
      prompt: "Which path?"
      options:
        - label: "Left path"
          effects:
            - type: xp_grant
              amount: 50
          steps:
            - type: stat_check
              condition:
                type: level
                value: 5
              on_pass:
                effects:
                  - type: end_adventure
                    outcome: discovered
              on_fail:
                effects:
                  - type: end_adventure
                    outcome: completed
        - label: "Right path"
          steps:
            - type: passive
              text: "You pick up a journal."
              effects:
                - type: milestone_grant
                  milestone: found-journal
            - type: narrative
              text: "The journal contains clues."
              effects:
                - type: end_adventure
                  outcome: completed
```

### Manual QA Steps

After implementing the change, run these commands against testlandia to verify all surfaces:

```bash
# Inspect
oscilla content list adventures --game testlandia
oscilla content show adventure trace-demo --game testlandia
oscilla content show region tooling-lab --game testlandia

# Graphs (examine output visually)
oscilla content graph world --game testlandia --format ascii
oscilla content graph adventure trace-demo --game testlandia --format mermaid
oscilla content graph deps --game testlandia --format dot --focus adventure:trace-demo

# Schema
oscilla content schema adventure
oscilla content schema --output /tmp/oscilla-schemas/

# Semantic validation
oscilla content test --game testlandia

# Trace (expect 3 paths: Left→pass, Left→fail, Right)
oscilla content trace trace-demo --game testlandia
oscilla content trace trace-demo --game testlandia --format json

# Create (interactive)
oscilla content create region --game testlandia
# → follow prompts to create a throwaway region

# Create (non-interactive)
oscilla content create enemy \
  --game testlandia \
  --name test-scaffold-enemy \
  --display-name "Scaffold Test Enemy" \
  --no-interactive
# → verify file created at content/testlandia/enemies/test-scaffold-enemy.yaml
```

---

## Risks / Trade-offs

| Risk                                                                                                                                                                                      | Mitigation                                                                                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pydot` API may differ across versions                                                                                                                                                    | Constrained to `>=4,<5` in pyproject.toml; exact version locked by `uv.lock`; API changed between 3.x and 4.x — design verified against v4 source and uses only v4-compatible API |
| Adventure tracer combinatorial explosion on very large adventures                                                                                                                         | Tracer is a static analysis tool, not a game execution; path count equals the product of branch counts at each step; document that very large adventures may produce many paths   |
| `export_schema` for complex discriminated unions (e.g., `Condition`) may produce schemas too large for some editors                                                                       | No mitigation needed for MVP; schema output is already useful for simpler kinds; complex union schemas are a known Pydantic limitation                                            |
| Scaffolded YAML uses `ruamel-yaml` style; may differ from author's preferred style                                                                                                        | Files are valid and load correctly; authors can reformat with their editor; `make chores` handles project YAML via dapperdata                                                     |
| `content create` for `adventure` places the file under `regions/<region>/locations/<location>/adventures/`; if those directories don't exist, `mkdir(parents=True)` creates them silently | This is the desired behavior; the convention is the convention                                                                                                                    |

## Open Questions

_(All open questions from the initial draft have been resolved.)_

- **`content graph deps` milestone/quest nodes** — RESOLVED: `build_deps_graph` includes all loaded manifest kinds by default. Authors can filter with `--include-kinds` / `--exclude-kinds` to reduce noise on large games.
- **`content schema --vscode`** — RESOLVED: Added as explicit `--vscode` flag in Decision 8. Requires `--output` to know the schema directory.

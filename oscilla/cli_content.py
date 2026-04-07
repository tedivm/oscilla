"""Author-facing content tooling subapp.

All commands are registered under ``oscilla content`` via:
    app.add_typer(content_app, name="content")
in oscilla/cli.py.
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table

from oscilla.engine.kinds import ALL_KINDS

logger = logging.getLogger(__name__)

content_app = typer.Typer(
    name="content",
    help="Content authoring tools: inspect, graph, validate, trace, scaffold.",
    no_args_is_help=True,
)

_console = Console()
_err_console = Console(stderr=True)

# OutputFormat type alias
OutputFormat = str  # "text" | "json" | "yaml"

# Maps plural CLI kind slug → (registry attribute name, singular display label)
# Singletons (game, character-config) are included but handled specially in list.
_KIND_MAP: Dict[str, Tuple[str, str]] = {k.plural_slug: (k.registry_attr, k.display_label) for k in ALL_KINDS}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_registry(game_name: str | None) -> "tuple[str, ContentRegistry]":
    """Load games and return a single (name, registry) pair.

    If game_name is given, load only that package. If omitted and exactly one
    game exists it is selected automatically. Raises SystemExit(1) on error.
    """
    from oscilla.engine.loader import ContentLoadError, load, load_games
    from oscilla.settings import settings

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
        f"[bold red]Multiple games found. Use --game to specify one: {', '.join(sorted(games))}[/bold red]"
    )
    raise SystemExit(1)


def _emit_structured_output(data: object, output_format: OutputFormat) -> None:
    """Serialize ``data`` to stdout in the requested format.

    This is the single point of truth for JSON/YAML serialization across all
    content commands. Call before any Rich rendering and return immediately.
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
        _err_console.print(f"[red]Unknown format {output_format!r}. Valid: text, json, yaml.[/red]")
        raise SystemExit(1)


def _manifest_summary(manifest: "ManifestEnvelope", kind_label: str) -> Dict[str, str]:
    """Return a flat dict of display-relevant fields for a manifest."""
    base: Dict[str, str] = {"name": manifest.metadata.name, "kind": kind_label}

    spec: Any = getattr(manifest, "spec", None)
    if spec is None:
        return base
    if hasattr(spec, "displayName"):
        base["display_name"] = spec.displayName
    if hasattr(spec, "description") and spec.description:
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
            base["repeatable"] = (
                "no" if not spec.repeatable else (str(spec.max_completions) if spec.max_completions else "yes")
            )
        case "Enemy":
            base["hp"] = str(spec.hp)
            base["attack"] = str(spec.attack)
            base["xp"] = str(spec.xp_reward)
        case "Item":
            base["category"] = spec.category
            base["labels"] = ", ".join(spec.labels) or "—"
    return base


def _print_spec_fields(manifest: "ManifestEnvelope") -> None:
    """Print all spec fields to the console in a human-readable way."""
    spec: Any = getattr(manifest, "spec", None)
    if spec is None:
        return
    for field_name, value in spec.__dict__.items():
        if field_name.startswith("_") or value is None:
            continue
        _console.print(f"  [dim]{field_name}:[/dim] {value}")


# ---------------------------------------------------------------------------
# content list
# ---------------------------------------------------------------------------


@content_app.command("list")
def content_list(
    kind: Annotated[str, typer.Argument(help=f"Manifest kind. One of: {', '.join(_KIND_MAP)}")],
    game: Annotated[Optional[str], typer.Option("--game", "-g", help="Game package name.")] = None,
    output_format: Annotated[str, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
) -> None:
    """List all manifests of a given kind in the content package."""
    from oscilla.engine.registry import KindRegistry

    kind = kind.lower()
    if kind not in _KIND_MAP:
        _err_console.print(f"[bold red]Unknown kind {kind!r}. Valid: {', '.join(_KIND_MAP)}[/bold red]")
        raise SystemExit(1)

    attr, label = _KIND_MAP[kind]
    _, registry = _resolve_registry(game)
    store = getattr(registry, attr)

    # Singletons (game, character-config) are ManifestEnvelope | None, not KindRegistry.
    if not isinstance(store, KindRegistry):
        if store is None:
            rows: List[Dict[str, str]] = []
        else:
            rows = [_manifest_summary(store, label)]
    else:
        rows = [_manifest_summary(m, label) for m in store.all()]

    if output_format != "text":
        _emit_structured_output(rows, output_format)
        return

    if not rows:
        _console.print(f"[yellow]No {label} manifests found.[/yellow]")
        return

    table = Table(title=f"{label} manifests ({len(rows)} total)")
    for col in rows[0]:
        table.add_column(col, style="cyan" if col == "name" else "")
    for row in rows:
        table.add_row(*[str(row[c]) for c in row])
    _console.print(table)


# ---------------------------------------------------------------------------
# content show
# ---------------------------------------------------------------------------


@content_app.command("show")
def content_show(
    kind: Annotated[str, typer.Argument(help="Manifest kind.")],
    name: Annotated[str, typer.Argument(help="Manifest name (metadata.name).")],
    game: Annotated[Optional[str], typer.Option("--game", "-g", help="Game package name.")] = None,
    output_format: Annotated[str, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
) -> None:
    """Print a detailed description of one manifest including cross-references."""
    from oscilla.engine.graph import build_manifest_xrefs
    from oscilla.engine.registry import KindRegistry

    kind = kind.lower().rstrip("s")  # allow both "adventure" and "adventures"
    # Normalize to plural slug
    singular_to_plural = {v[1].lower(): k for k, v in _KIND_MAP.items()}
    plural_slug = singular_to_plural.get(kind, kind + "s")

    if plural_slug not in _KIND_MAP:
        _err_console.print(f"[bold red]Unknown kind. Valid: {', '.join(_KIND_MAP)}[/bold red]")
        raise SystemExit(1)

    attr, label = _KIND_MAP[plural_slug]
    _, registry = _resolve_registry(game)
    store = getattr(registry, attr)

    if not isinstance(store, KindRegistry):
        # Singleton kinds (game, character-config)
        manifest = store if store is not None and store.metadata.name == name else None
    else:
        manifest = store.get(name)

    if manifest is None:
        _err_console.print(f"[bold red]{label} {name!r} not found.[/bold red]")
        raise SystemExit(1)

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


# ---------------------------------------------------------------------------
# content graph
# ---------------------------------------------------------------------------


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
    fmt: Annotated[str, typer.Option("--format", "-f", help="Output format: dot | mermaid | ascii")] = "ascii",
    focus: Annotated[
        Optional[str],
        typer.Option("--focus", help="For 'deps' type: focus node id, e.g. 'item:rusty-sword'."),
    ] = None,
    include_kinds: Annotated[
        Optional[str],
        typer.Option(
            "--include-kinds",
            help="For 'deps' type: comma-separated kind slugs to include (e.g. 'item,enemy').",
        ),
    ] = None,
    exclude_kinds: Annotated[
        Optional[str],
        typer.Option(
            "--exclude-kinds",
            help="For 'deps' type: comma-separated kind slugs to exclude (e.g. 'quest,milestone').",
        ),
    ] = None,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Write output to this file path instead of stdout."),
    ] = None,
) -> None:
    """Generate a graph visualization of game content."""
    from oscilla.engine.graph import build_adventure_graph, build_deps_graph, build_world_graph
    from oscilla.engine.graph_renderers import render

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

    built_graph = None
    match graph_type:
        case "world":
            built_graph = build_world_graph(registry)
        case "adventure":
            assert name is not None
            manifest = registry.adventures.get(name)
            if manifest is None:
                _err_console.print(f"[red]Adventure {name!r} not found.[/red]")
                raise SystemExit(1)
            built_graph = build_adventure_graph(manifest, registry)
        case "deps":
            built_graph = build_deps_graph(registry, focus=focus, include_kinds=include_set, exclude_kinds=exclude_set)

    assert built_graph is not None
    result = render(built_graph, fmt)  # type: ignore[arg-type]

    if output:
        Path(output).write_text(result)
        _console.print(f"[green]Written to {output}[/green]")
    else:
        typer.echo(result)


# ---------------------------------------------------------------------------
# content schema
# ---------------------------------------------------------------------------


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
        typer.Option(
            "--vscode",
            help=(
                "Write .vscode/settings.json yaml-language-server schema associations. "
                "Defaults output to .vscode/oscilla-schemas/ when --output is not provided."
            ),
        ),
    ] = False,
) -> None:
    """Export JSON Schema for Oscilla manifest kinds.

    With no KIND argument, all schemas are printed as a single JSON object keyed by kind.
    With --output and no KIND, writes one file per kind into the specified directory.
    With --vscode, also writes manifest.json and updates .vscode/settings.json with a
    content-path glob association. Output defaults to .vscode/oscilla-schemas/.
    """
    from oscilla.engine.schema_export import export_all_schemas, export_schema, export_union_schema

    # Resolve effective output: --vscode has a default; without --vscode, --output is optional.
    effective_output = output or (".vscode/oscilla-schemas" if vscode else None)

    if kind is not None:
        # Single-kind export: --vscode is not applicable here.
        try:
            schema = export_schema(kind)
        except ValueError as exc:
            _err_console.print(f"[red]{exc}[/red]")
            raise SystemExit(1)

        result = json.dumps(schema, indent=2)
        if effective_output:
            Path(effective_output).write_text(result)
            _console.print(f"[green]Written to {effective_output}[/green]")
        else:
            typer.echo(result)
        return

    # All schemas
    all_schemas = export_all_schemas()
    if effective_output:
        out_dir = Path(effective_output)
        out_dir.mkdir(parents=True, exist_ok=True)
        for k, schema in all_schemas.items():
            (out_dir / f"{k}.json").write_text(json.dumps(schema, indent=2))
        # Always write the union schema alongside per-kind schemas.
        (out_dir / "manifest.json").write_text(json.dumps(export_union_schema(), indent=2))
        _console.print(f"[green]Wrote {len(all_schemas) + 1} schema files to {out_dir}/[/green]")
        if vscode:
            _write_vscode_schema_associations(out_dir)
    else:
        typer.echo(json.dumps(all_schemas, indent=2))


def _write_vscode_schema_associations(
    schema_dir: Path,
) -> None:
    """Update .vscode/settings.json with a content-path glob pointing at manifest.json.

    A single glob covers all content files regardless of their filename, and works
    correctly with multi-document YAML files. The yaml-language-server validates
    each document independently against the discriminated union schema.

    Creates .vscode/settings.json if it does not exist. Merges into any existing
    yaml.schemas dict so that other schema associations are preserved.
    """
    import json as _json

    settings_path = Path(".vscode") / "settings.json"
    settings_path.parent.mkdir(exist_ok=True)
    try:
        existing: dict = _json.loads(settings_path.read_text()) if settings_path.exists() else {}
    except Exception:
        existing = {}
    # Use a relative path so the association is portable across machines.
    manifest_schema_path = str(schema_dir / "manifest.json")
    # **/*.yaml is safe because manifest.json uses an if/then guard on
    # apiVersion: oscilla/v1 — non-Oscilla files receive no validation.
    existing.setdefault("yaml.schemas", {})[manifest_schema_path] = "**/*.yaml"
    settings_path.write_text(_json.dumps(existing, indent=2))
    _console.print(f"[green]Updated {settings_path} with content glob → {manifest_schema_path}[/green]")


# ---------------------------------------------------------------------------
# content test
# ---------------------------------------------------------------------------


@content_app.command("test")
def content_test(
    game: Annotated[Optional[str], typer.Option("--game", "-g")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors.")] = False,
    output_format: Annotated[str, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
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


# ---------------------------------------------------------------------------
# content trace
# ---------------------------------------------------------------------------


@content_app.command("trace")
def content_trace(
    adventure_name: Annotated[str, typer.Argument(help="Adventure manifest name.")],
    game: Annotated[Optional[str], typer.Option("--game", "-g")] = None,
    output_format: Annotated[str, typer.Option("--format", "-F", help="Output format: text | json | yaml.")] = "text",
) -> None:
    """Trace all execution paths through an adventure (no character state changes)."""
    import dataclasses

    from oscilla.engine.tracer import trace_adventure

    _, registry = _resolve_registry(game)
    manifest = registry.adventures.get(adventure_name)
    if manifest is None:
        _err_console.print(f"[red]Adventure {adventure_name!r} not found.[/red]")
        raise SystemExit(1)

    result = trace_adventure(manifest)

    if output_format != "text":
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


# ---------------------------------------------------------------------------
# content create
# ---------------------------------------------------------------------------


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
        scaffold_location,
        scaffold_quest,
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
            game = typer.prompt("Game name", default=available[0])

    def _prompt_or_require(value: str | None, prompt_text: str, flag: str) -> str:
        if value:
            return value
        if no_interactive:
            _err_console.print(f"[red]{flag} is required in --no-interactive mode.[/red]")
            raise SystemExit(1)
        return str(typer.prompt(prompt_text))

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
        case _:
            _err_console.print(f"[red]Internal error: unhandled kind {kind!r}[/red]")
            raise SystemExit(1)

    _console.print(f"[bold green]✓ Created:[/bold green] {out_path}")
    _console.print(f"[dim]Open the file to fill in content. Validate with: oscilla validate --game {game}[/dim]")


# Type alias for type-checker — not evaluated at runtime.
if False:  # pragma: no cover
    from oscilla.engine.models.base import ManifestEnvelope
    from oscilla.engine.registry import ContentRegistry

import asyncio
import random
from functools import wraps
from typing import Callable, Coroutine, Dict, ParamSpec, TypeVar

import typer
from rich.prompt import Prompt

from .settings import settings

app = typer.Typer()


P = ParamSpec("P")
T = TypeVar("T")


def syncify(f: Callable[P, Coroutine[object, object, T]]) -> Callable[P, T]:
    """This simple decorator converts an async function into a sync function,
    allowing it to work with Typer.
    """

    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return asyncio.run(f(*args, **kwargs))

    return wrapper


@app.command(help="Install testing data for local development.")
@syncify
async def test_data() -> None:
    from . import __version__
    from .services.db import get_session, test_data

    typer.echo(f"{settings.project_name} - {__version__}")

    async with get_session() as session:
        await test_data(session)

    typer.echo("Development data installed successfully.")


@app.command(help=f"Display the current installed version of {settings.project_name}.")
def version() -> None:
    from . import __version__

    typer.echo(f"{settings.project_name} - {__version__}")


@app.command(help="Display a friendly greeting.")
def hello() -> None:
    typer.echo(f"Hello from {settings.project_name}!")


# ---------------------------------------------------------------------------
# Game engine commands
# ---------------------------------------------------------------------------


def _load_content() -> "ContentRegistry":
    """Load and validate the content package from CONTENT_PATH.

    Prints all validation errors and exits with code 1 on any failures so that
    the CLI exit code is reliable and shell scripts can detect content errors.
    """
    from oscilla.engine.loader import ContentLoadError, load
    from oscilla.engine.tui import console

    content_path = settings.content_path
    try:
        return load(content_path)
    except ContentLoadError as exc:
        console.print("[bold red]Content validation failed:[/bold red]")
        for error in exc.errors:
            console.print(f"  [red]•[/red] {error}")
        raise SystemExit(1)


def _select_region(
    player: "PlayerState",
    registry: "ContentRegistry",
    tui: "TUICallbacks",
) -> "str | None":
    """Filter accessible regions and return the chosen region ref, or None on Quit.

    Exits with code 1 if no regions are accessible — the root region must have
    no unlock condition in any valid content package.
    """
    from oscilla.engine.conditions import evaluate
    from oscilla.engine.tui import console

    accessible = [region for region in registry.regions.all() if evaluate(region.spec.effective_unlock, player)]
    if not accessible:
        console.print(
            "[bold red]Error: no accessible regions found.[/bold red] Ensure your root region has no unlock condition."
        )
        raise SystemExit(1)

    options = [r.spec.displayName for r in accessible] + ["Quit"]
    choice = tui.show_menu("Where would you like to go?", options)
    if choice == len(options):
        return None
    return accessible[choice - 1].metadata.name


def _select_location(
    player: "PlayerState",
    registry: "ContentRegistry",
    region_ref: str,
    tui: "TUICallbacks",
) -> "str | None":
    """Filter accessible locations in region_ref and return the chosen one, or None on Back.

    Returns None (Back) when no accessible locations exist — the player is
    never trapped.
    """
    from oscilla.engine.conditions import evaluate

    region = registry.regions.require(region_ref, "Region")
    accessible = [
        loc
        for loc in registry.locations.all()
        if loc.spec.region == region_ref and evaluate(loc.spec.effective_unlock, player)
    ]

    if not accessible:
        tui.show_text(f"There are no accessible locations in {region.spec.displayName} yet.")
        return None

    header = f"{region.spec.displayName}\n{region.spec.description}\n\nChoose a location:"
    tui.show_text(header)
    options = [loc.spec.displayName for loc in accessible] + ["Back"]
    choice = tui.show_menu("Location:", options)
    if choice == len(options):
        return None
    return accessible[choice - 1].metadata.name


def _pick_adventure(
    player: "PlayerState",
    registry: "ContentRegistry",
    location_ref: str,
) -> "str | None":
    """Return a weighted-random adventure ref from the eligible pool, or None.

    Filters pool entries by their requires condition, then draws one using
    random.choices with declared weights. Returns None on an empty pool.
    The caller must NOT record a location visit on a None result.
    Note: record_adventure_completed is handled internally by AdventurePipeline.run().
    """
    from oscilla.engine.conditions import evaluate

    location = registry.locations.require(location_ref, "Location")
    eligible = [entry for entry in location.spec.adventures if evaluate(entry.requires, player)]
    if not eligible:
        return None

    weights = [entry.weight for entry in eligible]
    (chosen,) = random.choices(population=eligible, weights=weights, k=1)
    return chosen.ref


_OUTCOME_MESSAGES: Dict[str, str] = {
    "completed": "Adventure complete!",
    "defeated": "You were defeated and barely escaped...",
    "fled": "You fled from battle.",
}


def _show_outcome(outcome: "AdventureOutcome", tui: "TUICallbacks") -> None:
    """Display the adventure result via the TUI interface.

    Using tui.show_text() keeps cli.py free of direct Rich imports and makes
    outcome display testable via MockTUI.
    """
    message = _OUTCOME_MESSAGES.get(outcome.value, f"Adventure ended: {outcome.value}")
    tui.show_text(message)


@app.command(help="Start the interactive game loop.")
def game() -> None:
    """Load content, create a character, and enter the adventure loop."""
    from oscilla.engine.pipeline import AdventurePipeline
    from oscilla.engine.player import PlayerState
    from oscilla.engine.tui import RichTUI, console, show_status

    registry = _load_content()

    if registry.game is None:
        typer.echo("Error: no Game manifest found in content.", err=True)
        raise SystemExit(1)
    if registry.character_config is None:
        typer.echo("Error: no CharacterConfig manifest found in content.", err=True)
        raise SystemExit(1)

    name = Prompt.ask("[bold]Character name[/bold]")
    player = PlayerState.new_player(
        name=name,
        game_manifest=registry.game,
        character_config=registry.character_config,
    )
    tui = RichTUI()

    while True:
        show_status(player=player, registry=registry)

        region_ref = _select_region(player=player, registry=registry, tui=tui)
        if region_ref is None:
            break

        location_ref = _select_location(
            player=player,
            registry=registry,
            region_ref=region_ref,
            tui=tui,
        )
        if location_ref is None:
            continue

        adventure_ref = _pick_adventure(
            player=player,
            registry=registry,
            location_ref=location_ref,
        )
        if adventure_ref is None:
            tui.show_text("No adventures are available here right now.")
            continue

        # Record the visit only after confirming an adventure will run.
        player.statistics.record_location_visited(location_ref)

        pipeline = AdventurePipeline(registry=registry, player=player, tui=tui)
        outcome = pipeline.run(adventure_ref)
        _show_outcome(outcome=outcome, tui=tui)
        show_status(player=player, registry=registry)

    console.print("\n[bold]Goodbye![/bold]")


@app.command(help="Validate the content package and report any errors.")
def validate() -> None:
    """Load and validate all manifests, then print a summary or error list."""
    from oscilla.engine.loader import ContentLoadError, load
    from oscilla.engine.tui import console

    content_path = settings.content_path
    try:
        registry = load(content_path)
    except ContentLoadError as exc:
        console.print(f"[bold red]✗ {len(exc.errors)} error(s) found:[/bold red]\n")
        for error in exc.errors:
            console.print(f"  [red]•[/red] {error}")
        raise SystemExit(1)

    counts = {
        "regions": len(registry.regions),
        "locations": len(registry.locations),
        "adventures": len(registry.adventures),
        "enemies": len(registry.enemies),
        "items": len(registry.items),
        "recipes": len(registry.recipes),
        "quests": len(registry.quests),
        "classes": len(registry.classes),
    }
    summary = ", ".join(f"{count} {kind}" for kind, count in counts.items() if count > 0)
    console.print(f"[bold green]✓ Loaded {summary}[/bold green]")


# Type aliases used in function signatures above (avoid runtime import cost)
if False:  # TYPE_CHECKING block — never executes at runtime
    from oscilla.engine.pipeline import AdventureOutcome, TUICallbacks
    from oscilla.engine.player import PlayerState
    from oscilla.engine.registry import ContentRegistry


if __name__ == "__main__":
    app()

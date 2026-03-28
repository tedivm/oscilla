import asyncio
from functools import wraps
from typing import Callable, Coroutine, ParamSpec, TypeVar

import typer

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
    from rich.console import Console

    from oscilla.engine.loader import ContentLoadError, load

    _console = Console()
    content_path = settings.content_path
    try:
        return load(content_path)
    except ContentLoadError as exc:
        _console.print("[bold red]Content validation failed:[/bold red]")
        for error in exc.errors:
            _console.print(f"  [red]•[/red] {error}")
        raise SystemExit(1)


@app.command(help="Start the interactive game loop.")
def game() -> None:
    """Load content and launch the full-screen Textual game application."""
    from oscilla.engine.tui import OscillaApp

    registry = _load_content()

    if registry.game is None:
        typer.echo("Error: no Game manifest found in content.", err=True)
        raise SystemExit(1)
    if registry.character_config is None:
        typer.echo("Error: no CharacterConfig manifest found in content.", err=True)
        raise SystemExit(1)

    # app.run() is the synchronous Textual entry point — no @syncify needed.
    OscillaApp(registry=registry).run()


@app.command(help="Validate the content package and report any errors.")
def validate() -> None:
    """Load and validate all manifests, then print a summary or error list."""
    from rich.console import Console

    from oscilla.engine.loader import ContentLoadError, load

    _console = Console()
    content_path = settings.content_path
    try:
        registry = load(content_path)
    except ContentLoadError as exc:
        _console.print(f"[bold red]✗ {len(exc.errors)} error(s) found:[/bold red]\n")
        for error in exc.errors:
            _console.print(f"  [red]•[/red] {error}")
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
    _console.print(f"[bold green]✓ Loaded {summary}[/bold green]")


# Type alias used purely for type checkers — never evaluated at runtime
if False:  # pragma: no cover
    from oscilla.engine.registry import ContentRegistry


if __name__ == "__main__":
    app()

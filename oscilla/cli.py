import asyncio
from functools import wraps
from typing import Annotated, Callable, Coroutine, ParamSpec, TypeVar

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
@syncify
async def game(
    character_name: Annotated[
        str | None, typer.Option("--character-name", "-c", help="Character name to load or create.")
    ] = None,
    reset_db: Annotated[
        bool,
        typer.Option(
            "--reset-db/--no-reset-db",
            help="Delete all saved characters for the current user before starting.",
        ),
    ] = False,
) -> None:
    """Load content, resolve user identity, select or create a character, and launch the game."""
    from oscilla.engine.tui import OscillaApp
    from oscilla.services.character import delete_user_characters
    from oscilla.services.db import get_session
    from oscilla.services.user import derive_tui_user_key, get_or_create_user

    registry = _load_content()

    if registry.game is None:
        typer.echo("Error: no Game manifest found in content.", err=True)
        raise SystemExit(1)
    if registry.character_config is None:
        typer.echo("Error: no CharacterConfig manifest found in content.", err=True)
        raise SystemExit(1)

    if reset_db:
        typer.confirm(
            "This will permanently delete all saved characters for the current user. Continue?",
            abort=True,
        )
        async with get_session() as session:
            user_key = derive_tui_user_key()
            user = await get_or_create_user(session=session, user_key=user_key)
            count = await delete_user_characters(session=session, user_id=user.id)
        typer.echo(f"Deleted {count} character(s).")

    await OscillaApp(registry=registry, character_name=character_name).run_async()

    # Explicitly dispose the connection pool after the TUI exits so that any
    # remaining aiosqlite connections are closed while the event loop is still
    # running cleanly.  Without this, garbage-collected pool connections can
    # trigger a CancelledError during their async rollback.
    from oscilla.services.db import engine

    await engine.dispose()


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

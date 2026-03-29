import asyncio
from functools import wraps
from typing import Annotated, Callable, Coroutine, Dict, ParamSpec, TypeVar

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


def _load_games() -> "Dict[str, ContentRegistry]":
    """Load all game packages from GAMES_PATH.

    Prints all validation errors and exits with code 1 on any failures so that
    the CLI exit code is reliable and shell scripts can detect content errors.
    """
    from rich.console import Console

    from oscilla.engine.loader import ContentLoadError, load_games

    _console = Console()
    try:
        return load_games(settings.games_path)
    except ContentLoadError as exc:
        _console.print("[bold red]Content validation failed:[/bold red]")
        for error in exc.errors:
            _console.print(f"  [red]•[/red] {error}")
        raise SystemExit(1)


@app.command(help="Start the interactive game loop.")
@syncify
async def game(
    game_name: Annotated[
        str | None, typer.Option("--game", "-g", help="Game package directory name to launch.")
    ] = None,
    character_name: Annotated[
        str | None, typer.Option("--character-name", "-c", help="Character name to load or create.")
    ] = None,
    reset_db: Annotated[
        bool,
        typer.Option(
            "--reset-db/--no-reset-db",
            help="Delete all saved characters for the current user in the chosen game before starting.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompts (for use with --reset-db)."),
    ] = False,
) -> None:
    """Load games, resolve user identity, select or create a character, and launch the game."""
    from oscilla.engine.tui import OscillaApp
    from oscilla.services.character import delete_user_characters
    from oscilla.services.db import get_session
    from oscilla.services.user import derive_tui_user_key, get_or_create_user

    games = _load_games()

    if not games:
        typer.echo("Error: no game packages found in GAMES_PATH.", err=True)
        raise SystemExit(1)

    if game_name is None:
        if len(games) == 1:
            game_name = next(iter(games))
        else:
            # Let TUI handle game selection
            try:
                await OscillaApp(games=games, game_name=None, character_name=character_name).run_async()
            finally:
                # Force terminal state cleanup even on abnormal exit
                import sys

                sys.stdout.write("\033[?1049l")  # rmcup - exit alternate screen
                sys.stdout.flush()

            # Dispose the connection pool after TUI exits
            from oscilla.services.db import engine

            await engine.dispose()
            return

    if game_name not in games:
        typer.echo(f"Error: game {game_name!r} not found. Available: {', '.join(sorted(games))}", err=True)
        raise SystemExit(1)

    registry = games[game_name]

    if registry.game is None:
        typer.echo(f"Error: no Game manifest found in {game_name!r}.", err=True)
        raise SystemExit(1)
    if registry.character_config is None:
        typer.echo(f"Error: no CharacterConfig manifest found in {game_name!r}.", err=True)
        raise SystemExit(1)

    if reset_db:
        if not force:
            typer.confirm(
                f"This will permanently delete all saved characters for the current user in {game_name!r}. Continue?",
                abort=True,
            )
        async with get_session() as session:
            user_key = derive_tui_user_key()
            user = await get_or_create_user(session=session, user_key=user_key)
            count = await delete_user_characters(session=session, user_id=user.id, game_name=game_name)
        typer.echo(f"Deleted {count} character(s).")

    try:
        await OscillaApp(games={game_name: registry}, game_name=game_name, character_name=character_name).run_async()
    finally:
        # Force terminal state cleanup even on abnormal exit
        import sys

        sys.stdout.write("\033[?1049l")  # rmcup - exit alternate screen
        sys.stdout.flush()

    # Explicitly dispose the connection pool after the TUI exits so that any
    # remaining aiosqlite connections are closed while the event loop is still
    # running cleanly.  Without this, garbage-collected pool connections can
    # trigger a CancelledError during their async rollback.
    from oscilla.services.db import engine

    await engine.dispose()


@app.command(help="Validate all game packages and report any errors.")
def validate(
    game_name: Annotated[str | None, typer.Option("--game", "-g", help="Validate only this game package.")] = None,
) -> None:
    """Load and validate all manifests in GAMES_PATH, then print a summary or error list."""
    from rich.console import Console

    from oscilla.engine.loader import ContentLoadError, load, load_games

    _console = Console()

    if game_name is not None:
        # Validate a single game package
        game_path = settings.games_path / game_name
        if not game_path.is_dir():
            _console.print(f"[bold red]✗ Game package {game_name!r} not found in GAMES_PATH[/bold red]")
            raise SystemExit(1)
        try:
            registry = load(game_path)
        except ContentLoadError as exc:
            _console.print(f"[bold red]✗ {game_name}: {len(exc.errors)} error(s) found:[/bold red]\n")
            for error in exc.errors:
                _console.print(f"  [red]•[/red] {error}")
            raise SystemExit(1)
        games = {game_name: registry}
    else:
        try:
            games = load_games(settings.games_path)
        except ContentLoadError as exc:
            _console.print(f"[bold red]✗ {len(exc.errors)} error(s) found:[/bold red]\n")
            for error in exc.errors:
                _console.print(f"  [red]•[/red] {error}")
            raise SystemExit(1)

    for pkg_name, registry in sorted(games.items()):
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
        _console.print(f"[bold green]✓ {pkg_name}: {summary}[/bold green]")


# Type alias used purely for type checkers — never evaluated at runtime
if False:  # pragma: no cover
    from oscilla.engine.registry import ContentRegistry


if __name__ == "__main__":
    app()

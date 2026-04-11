import asyncio
import io
import json
import logging
import sys
from functools import wraps
from typing import Annotated, Any, Callable, Coroutine, Dict, List, ParamSpec, TypeVar

import platformdirs
import typer
from rich.console import Console
from rich.panel import Panel

from oscilla.engine.loader import ContentLoadError, LoadWarning, load_from_disk, load_from_text, load_games
from oscilla.engine.semantic_validator import validate_semantic
from oscilla.engine.tui import OscillaApp
from oscilla.services.character import delete_user_characters
from oscilla.services.user import derive_tui_user_key, get_or_create_user

from . import __version__
from .cli_content import content_app
from .services.crash import _GITHUB_ISSUES_URL, write_crash_report
from .services.db import engine, get_session, migrate_database
from .services.db import test_data as _install_test_data
from .settings import settings

logger = logging.getLogger(__name__)

app = typer.Typer()
app.add_typer(content_app, name="content")


def _configure_logging() -> None:
    """Enable file-based debug logging when settings.debug is True.

    Logging is off by default so that distributed builds do not create log
    files without the user opting in.  Enable it by setting DEBUG=true in
    your .env file (see .env.example).
    """
    if not settings.debug:
        return
    log_path = platformdirs.user_data_path("oscilla") / "oscilla.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        filename=str(log_path),
        encoding="utf-8",
    )


def _handle_crash(exc: BaseException) -> None:
    """Write a crash report and display a summary to the user.

    Must be called after the TUI has already restored the terminal so that
    Rich console output is visible to the user.
    """
    crash_path = write_crash_report(exc)
    console = Console(stderr=True)
    console.print(
        Panel(
            f"[bold]{type(exc).__name__}:[/bold] {exc}\n\n"
            f"Crash report saved to: [bold]{crash_path}[/bold]\n"
            f"Please include this file when reporting the bug at "
            f"[link={_GITHUB_ISSUES_URL}]{_GITHUB_ISSUES_URL}[/link]",
            title="[bold red]Oscilla crashed unexpectedly[/bold red]",
            border_style="red",
        )
    )


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
    typer.echo(f"{settings.project_name} - {__version__}")

    async with get_session() as session:
        await _install_test_data(session)

    typer.echo("Development data installed successfully.")


@app.command(help=f"Display the current installed version of {settings.project_name}.")
def version() -> None:
    typer.echo(f"{settings.project_name} - {__version__}")


@app.command(help="Display a friendly greeting.")
def hello() -> None:
    typer.echo(f"Hello from {settings.project_name}!")


@app.command(help="Print the path to the user data directory used by Oscilla.")
def data_path() -> None:
    typer.echo(str(platformdirs.user_data_path("oscilla")))


# ---------------------------------------------------------------------------
# Game engine commands
# ---------------------------------------------------------------------------


def _load_games() -> "Dict[str, ContentRegistry]":
    """Load all game packages from GAMES_PATH.

    Prints all validation errors and exits with code 1 on any failures so that
    the CLI exit code is reliable and shell scripts can detect content errors.
    Warnings are surfaced via the logger but do not cause early exit.
    """
    _console = Console(stderr=True)
    try:
        games, all_warnings = load_games(settings.games_path)
        for pkg_name, warnings in all_warnings.items():
            for warning in warnings:
                logger.warning("[%s] %s", pkg_name, warning)
        return games
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
    migrate_database()
    _configure_logging()

    games = _load_games()

    if not games:
        typer.echo("Error: no game packages found in GAMES_PATH.", err=True)
        raise SystemExit(1)

    if reset_db:
        games_to_reset = [game_name] if game_name else list(games)
        if not force:
            scope = f"{game_name!r}" if game_name else "ALL games"
            typer.confirm(
                f"This will permanently delete all saved characters for the current user in {scope}. Continue?",
                abort=True,
            )
        async with get_session() as session:
            user_key = derive_tui_user_key()
            user = await get_or_create_user(session=session, user_key=user_key)
            count = 0
            for gname in games_to_reset:
                count += await delete_user_characters(session=session, user_id=user.id, game_name=gname)
        typer.echo(f"Deleted {count} character(s).")

    if game_name is None:
        if len(games) == 1:
            game_name = next(iter(games))
        else:
            # Let TUI handle game selection
            tui_crashed = False
            try:
                await OscillaApp(games=games, game_name=None, character_name=character_name).run_async()
            except Exception as exc:
                tui_crashed = True
                _handle_crash(exc)
            finally:
                # Force terminal state cleanup even on abnormal exit
                sys.stdout.write("\033[?1049l")  # rmcup - exit alternate screen
                sys.stdout.flush()

            if tui_crashed:
                raise SystemExit(1)

            # Dispose the connection pool after TUI exits
            try:
                await engine.dispose()
            except asyncio.CancelledError:
                # Suppress CancelledError during shutdown cleanup
                pass
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

    tui_crashed = False
    try:
        await OscillaApp(games={game_name: registry}, game_name=game_name, character_name=character_name).run_async()
    except Exception as exc:
        tui_crashed = True
        _handle_crash(exc)
    finally:
        # Force terminal state cleanup even on abnormal exit
        sys.stdout.write("\033[?1049l")  # rmcup - exit alternate screen
        sys.stdout.flush()

    if tui_crashed:
        raise SystemExit(1)

    # Explicitly dispose the connection pool after the TUI exits so that any
    # remaining aiosqlite connections are closed while the event loop is still
    # running cleanly.  Without this, garbage-collected pool connections can
    # trigger a CancelledError during their async rollback.
    try:
        await engine.dispose()
    except asyncio.CancelledError:
        # If the event loop is being cancelled during shutdown, suppress the
        # CancelledError from SQLAlchemy connection cleanup to avoid showing
        # a spurious error to the user.
        pass


@app.command(help="Validate game packages or manifest content and report errors and warnings.")
def validate(
    game_name: Annotated[
        str | None,
        typer.Option("--game", "-g", help="Validate only this game package (ignored when --stdin is used)."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Treat warnings as errors and exit with code 1 if any are found."),
    ] = False,
    no_semantic: Annotated[
        bool,
        typer.Option(
            "--no-semantic",
            help="Skip semantic checks (undefined refs, circular chains, orphaned/unreachable content).",
        ),
    ] = False,
    no_references: Annotated[
        bool,
        typer.Option(
            "--no-references",
            help="Skip cross-manifest reference validation.",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-F", help="Output format: text | json | yaml."),
    ] = "text",
    stdin: Annotated[
        bool,
        typer.Option(
            "--stdin",
            help="Read YAML manifest content from stdin instead of from GAMES_PATH. Ignores --game.",
        ),
    ] = False,
) -> None:
    """Load and validate manifests from disk or stdin, then report errors and warnings."""
    if stdin:
        _validate_stdin(
            output_format=output_format,
            strict=strict,
            no_semantic=no_semantic,
            no_references=no_references,
        )
    else:
        _validate_games(
            game_name=game_name,
            output_format=output_format,
            strict=strict,
            no_semantic=no_semantic,
            no_references=no_references,
        )


def _validate_stdin(
    output_format: str,
    strict: bool,
    no_semantic: bool,
    no_references: bool,
) -> None:
    """Validate YAML manifests piped to stdin."""
    _console = Console(stderr=True)

    text = sys.stdin.read()
    if not text.strip():
        _console.print("[bold red]✗ No content provided on stdin.[/bold red]")
        raise SystemExit(1)

    try:
        registry, load_warnings = load_from_text(text, skip_references=no_references)
    except ContentLoadError as exc:
        error_list: List[Dict[str, Any]] = [{"message": str(e)} for e in exc.errors]
        _render_validate_output(
            output_format=output_format,
            strict=strict,
            pkg_summaries={"<stdin>": {}},
            error_list=error_list,
            warning_list=[],
        )
        raise SystemExit(1)

    pkg_summaries: Dict[str, Dict[str, int]] = {"<stdin>": _registry_summary(registry)}
    warning_list: List[Dict[str, Any]] = [{"message": str(w)} for w in load_warnings]
    error_list = []

    if not no_semantic:
        for issue in validate_semantic(registry):
            if issue.severity == "error":
                error_list.append({"kind": issue.kind, "message": issue.message, "manifest": issue.manifest})
            else:
                warning_list.append({"kind": issue.kind, "message": issue.message, "manifest": issue.manifest})

    _render_validate_output(
        output_format=output_format,
        strict=strict,
        pkg_summaries=pkg_summaries,
        error_list=error_list,
        warning_list=warning_list,
    )
    if error_list or (strict and warning_list):
        raise SystemExit(1)


def _validate_games(
    game_name: str | None,
    output_format: str,
    strict: bool,
    no_semantic: bool,
    no_references: bool,
) -> None:
    """Validate game packages from disk."""
    all_pkg_warnings: Dict[str, List[LoadWarning]] = {}

    if game_name is not None:
        game_path = settings.games_path / game_name
        if not game_path.is_dir():
            error_list: List[Dict[str, Any]] = [{"message": f"Game package {game_name!r} not found in GAMES_PATH"}]
            _render_validate_output(output_format, strict, {}, error_list, [])
            raise SystemExit(1)
        try:
            registry, warnings = load_from_disk(game_path)
        except ContentLoadError as exc:
            error_list = [{"message": str(e)} for e in exc.errors]
            _render_validate_output(output_format, strict, {}, error_list, [])
            raise SystemExit(1)
        games = {game_name: registry}
        all_pkg_warnings[game_name] = warnings
    else:
        try:
            games, all_pkg_warnings = load_games(settings.games_path)
        except ContentLoadError as exc:
            error_list = [{"message": str(e)} for e in exc.errors]
            _render_validate_output(output_format, strict, {}, error_list, [])
            raise SystemExit(1)

    pkg_summaries: Dict[str, Dict[str, int]] = {}
    error_list = []
    warning_list: List[Dict[str, Any]] = []

    for pkg_name, registry in sorted(games.items()):
        pkg_summaries[pkg_name] = _registry_summary(registry)
        for w in all_pkg_warnings.get(pkg_name, []):
            warning_list.append({"message": str(w)})

    if not no_semantic:
        for pkg_name, registry in sorted(games.items()):
            for issue in validate_semantic(registry):
                entry: Dict[str, Any] = {
                    "kind": issue.kind,
                    "message": issue.message,
                    "manifest": issue.manifest,
                    "package": pkg_name,
                }
                if issue.severity == "error":
                    error_list.append(entry)
                else:
                    warning_list.append(entry)

    _render_validate_output(
        output_format=output_format,
        strict=strict,
        pkg_summaries=pkg_summaries,
        error_list=error_list,
        warning_list=warning_list,
    )
    if error_list or (strict and warning_list):
        raise SystemExit(1)


def _render_validate_output(
    output_format: str,
    strict: bool,
    pkg_summaries: Dict[str, Dict[str, int]],
    error_list: List[Dict[str, Any]],
    warning_list: List[Dict[str, Any]],
) -> None:
    """Emit validation results in the requested format.

    For text output: prints per-package summary lines, then errors/warnings.
    For json/yaml: emits a single structured document to stdout.
    """
    if output_format != "text":
        _emit_structured_output(
            {"errors": error_list, "warnings": warning_list, "summary": pkg_summaries},
            output_format,
        )
        return

    _console = Console()
    # Text output: print one summary line per package.
    for pkg_name, counts in pkg_summaries.items():
        if counts:
            summary_str = ", ".join(f"{count} {kind}" for kind, count in counts.items())
            _console.print(f"[bold green]✓ {pkg_name}: {summary_str}[/bold green]")
        else:
            _console.print(f"[bold green]✓ {pkg_name}[/bold green]")

    for entry in warning_list:
        color = "bold red" if strict else "yellow"
        kind_tag = f"[{entry['kind']}] " if "kind" in entry else ""
        pkg_tag = f"[{entry['package']}] " if "package" in entry else ""
        _console.print(f"  [{color}]⚠[/{color}] {pkg_tag}{kind_tag}{entry['message']}")

    for entry in error_list:
        kind_tag = f"[{entry['kind']}] " if "kind" in entry else ""
        pkg_tag = f"[{entry['package']}] " if "package" in entry else ""
        _console.print(f"  [red]✗[/red] {pkg_tag}{kind_tag}{entry['message']}")

    if strict and warning_list:
        _console.print(f"\n[bold red]Strict mode: {len(warning_list)} warning(s) treated as errors.[/bold red]")


def _registry_summary(registry: "ContentRegistry") -> Dict[str, int]:
    """Build a non-zero count summary from a ContentRegistry."""
    counts = {
        "regions": len(registry.regions),
        "locations": len(registry.locations),
        "adventures": len(registry.adventures),
        "archetypes": len(registry.archetypes),
        "enemies": len(registry.enemies),
        "items": len(registry.items),
        "recipes": len(registry.recipes),
        "quests": len(registry.quests),
    }
    return {k: v for k, v in counts.items() if v > 0}


def _emit_structured_output(data: object, output_format: str) -> None:
    """Serialize data to stdout in the requested format."""
    if output_format == "json":
        typer.echo(json.dumps(data, indent=2, default=str))
    elif output_format == "yaml":
        from ruamel.yaml import YAML as _YAML

        _y = _YAML()
        _y.default_flow_style = False
        buf = io.StringIO()
        _y.dump(data, buf)
        typer.echo(buf.getvalue())
    else:
        Console(stderr=True).print(f"[red]Unknown format {output_format!r}. Valid: text, json, yaml.[/red]")
        raise SystemExit(1)


# Type alias used purely for type checkers — never evaluated at runtime
if False:  # pragma: no cover
    from oscilla.engine.registry import ContentRegistry


if __name__ == "__main__":
    app()

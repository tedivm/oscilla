---
name: typer-cli
description: "Add or modify CLI commands in Oscilla using Typer. Use when: adding new CLI subcommands, wrapping async functions for CLI use, understanding the CLI entrypoint structure, or following the @syncify pattern for async commands."
---

# Typer CLI

> **context7**: If the `mcp_context7` tool is available, resolve and load the full `typer` documentation before making any changes to the CLI system:
> ```
> mcp_context7_resolve-library-id: "typer"
> mcp_context7_get-library-docs: <resolved-id>
> ```

Any command or script that must be accessible to users must be exposed through the Typer library.

For full developer documentation see [docs/dev/cli.md](../../docs/dev/cli.md).

---

## CLI Structure

The CLI is registered in `pyproject.toml` as a project script:

```toml
[project.scripts]
oscilla = "oscilla.cli:app"
```

After installation, the `oscilla` command is available. The main app is defined in `oscilla/cli.py`. Domain-specific subcommand groups live in separate `oscilla/cli_<domain>.py` files and are mounted onto the main app.

### Current Command Tree

```
oscilla
├── game              # Launch the interactive TUI game loop
├── validate          # Validate game package manifests (also: oscilla validate)
├── version           # Print installed version
├── hello             # Friendly greeting (development helper)
├── data-path         # Print the user data directory path
├── test-data         # Install test/development data into the database
└── content           # Content authoring subcommands (oscilla/cli_content.py)
    ├── list          # List all manifests of a given kind
    ├── show          # Inspect one manifest with cross-references
    ├── graph         # Visualize world/adventure/dependency graphs
    ├── trace         # Trace all execution paths through an adventure
    ├── schema        # Export JSON Schema for manifest kinds
    └── create        # Scaffold a new manifest file
```

The `content` subapp is defined in `oscilla/cli_content.py` and mounted in `cli.py`:

```python
from .cli_content import content_app

app.add_typer(content_app, name="content")
```

---

## Async Commands — `@syncify`

Typer runs commands synchronously, but Oscilla uses async throughout (database access, HTTP calls, etc.). Use the `@syncify` decorator from `oscilla/cli.py` to bridge them:

```python
from oscilla.cli import syncify

@app.command()
@syncify
async def my_command(name: str) -> None:
    """This async function will run correctly from the CLI."""
    result = await some_async_operation(name)
    typer.echo(result)
```

**Critical**: `@app.command()` must appear **before** `@syncify` in decorator order. Do **not** use `asyncio.run()` directly — `syncify` handles the event loop correctly.

### Database Access in CLI Commands

Use `get_session` from `oscilla.services.db` for database-backed commands. Always use it as an async context manager:

```python
from oscilla.services.db import get_session

@app.command()
@syncify
async def my_db_command() -> None:
    """Example command using database access."""
    async with get_session() as session:
        result = await session.execute(select(MyModel))
        items = result.scalars().all()
        for item in items:
            typer.echo(item.name)
```

For commands that need database migrations applied first, call `migrate_database()` at the top of the command (see the `game` command as a reference).

---

## Parameter Pattern

Use `Annotated[]` for all arguments and options — it keeps the signature clean and is the Typer-recommended style:

```python
import typer
from typing import Annotated


app = typer.Typer()


@app.command()
def process(
    input_file: Annotated[str, typer.Argument(help="Path to the input file")],
    output_file: Annotated[str | None, typer.Option(help="Path to the output file")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    """Process the input file and generate output."""
    if verbose:
        typer.echo(f"Processing {input_file}...")
    typer.echo("Done!")


@app.command()
@syncify
async def fetch(
    url: Annotated[str, typer.Argument(help="URL to fetch data from")],
) -> None:
    """Fetch data from a URL asynchronously."""
    data = await fetch_url(url)
    typer.echo(data)
```

### Arguments vs Options

| Type                     | Typer class        | CLI usage                  |
| ------------------------ | ------------------ | -------------------------- |
| Positional (required)    | `typer.Argument()` | `oscilla my-cmd value`     |
| Named flag/option        | `typer.Option()`   | `oscilla my-cmd --flag x`  |
| Boolean flag pair        | `typer.Option("--yes/--no")` | `oscilla my-cmd --yes` |

### Output Format Pattern

Many existing commands support `--format text|json|yaml`. When adding a command that returns structured data, follow this pattern from `cli_content.py`:

```python
output_format: Annotated[
    str,
    typer.Option("--format", "-F", help="Output format: text | json | yaml."),
] = "text"
```

Use `_emit_structured_output(data, output_format)` (defined in `cli_content.py`) for JSON/YAML output, and Rich tables/panels for `text` output.

---

## Adding a New Command Group

Create `oscilla/cli_<domain>.py`:

```python
# oscilla/cli_reports.py
import typer
from typing import Annotated

reports_app = typer.Typer(
    name="reports",
    help="Report generation commands.",
    no_args_is_help=True,
)


@reports_app.command("generate")
def generate_report(
    output: Annotated[str, typer.Argument(help="Output file path")],
) -> None:
    """Generate a report and write it to the output path."""
    ...
```

Then mount it in `oscilla/cli.py`:

```python
from .cli_reports import reports_app

app.add_typer(reports_app, name="reports")
```

Use `no_args_is_help=True` on subapp `Typer()` instances so that `oscilla reports` without arguments shows help rather than an error.

---

## Output: Rich vs `typer.echo`

- Use `typer.echo()` for simple single-line output.
- Use `rich.console.Console` and Rich components (tables, panels) for formatted multi-line output — this is the pattern used throughout `cli_content.py`.
- For error output, write to stderr: `Console(stderr=True)` or `typer.echo(..., err=True)`.
- Exit with a non-zero code on failure: `raise SystemExit(1)`.

---

## Error Handling Pattern

Follow the pattern used in existing commands: print a Rich-formatted error to stderr and raise `SystemExit(1)`:

```python
from rich.console import Console

_err_console = Console(stderr=True)

@app.command()
def my_command(name: str) -> None:
    """..."""
    item = lookup(name)
    if item is None:
        _err_console.print(f"[bold red]{name!r} not found.[/bold red]")
        raise SystemExit(1)
    typer.echo(item)
```

---

## Style Checklist

- [ ] New commands in `oscilla/cli.py` or `oscilla/cli_<domain>.py`
- [ ] Async commands use `@syncify` (not `asyncio.run()`)
- [ ] `@app.command()` decorator appears **before** `@syncify`
- [ ] All parameters use `Annotated[type, typer.Argument/Option(...)]`
- [ ] Every command has a docstring (used as `--help` text)
- [ ] Subapp `Typer()` instances use `no_args_is_help=True`
- [ ] New subapp mounted in `oscilla/cli.py` with `app.add_typer(...)`
- [ ] Error output goes to stderr via `Console(stderr=True)` or `err=True`
- [ ] Failures raise `SystemExit(1)` (not `sys.exit(1)` or exceptions)

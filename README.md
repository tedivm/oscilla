# oscilla



## Installation

```bash
pip install oscilla
```

## Playing Locally

Oscilla requires a content package — a directory of YAML manifests that define the game world. By default it looks for a `content/` directory in the project root. You can point it at any content package with the `CONTENT_PATH` environment variable.

```bash
# Validate your content package before playing
uv run oscilla validate

# Start an interactive game session
uv run oscilla game

# Use a custom content directory
CONTENT_PATH=/path/to/my-content uv run oscilla game
```

## CLI

All commands are available via `oscilla`. Run any command with `--help` for full usage.

```bash
uv run oscilla --help
```

### `game` — Play

Launches the interactive terminal UI. The game resolves your user identity from the system environment, then lets you select or create a character.

```bash
uv run oscilla game
```

| Option | Short | Description |
|---|---|---|
| `--character-name NAME` | `-c NAME` | Load or create the character with this name, skipping the selection screen. |
| `--reset-db` | | Delete all saved characters for the current user before starting. Prompts for confirmation. |

**Examples**

```bash
# Jump straight into a named character
uv run oscilla game --character-name "Aldric"

# Wipe your save data and start fresh
uv run oscilla game --reset-db

# Combine: reset, then immediately start a named character
uv run oscilla game --reset-db --character-name "Aldric"
```

> **Note:** `--reset-db` permanently deletes all characters associated with your user. The CLI will ask for confirmation before proceeding.

### `validate` — Check Content

Loads and validates the entire content package, printing a summary on success or a list of errors on failure. Exits with code 1 if any errors are found, making it suitable for CI pipelines.

```bash
uv run oscilla validate
```

### `version` — Show Version

Prints the installed version of Oscilla.

```bash
uv run oscilla version
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CONTENT_PATH` | `content/` | Path to the content package directory. |
| `DATABASE_URL` | auto-derived SQLite path | SQLAlchemy async database URL for character persistence. |

## Developer Documentation

Comprehensive developer documentation is available in [`docs/dev/`](./docs/dev/) covering testing, configuration, deployment, and all project features.

### Quick Start for Developers

```bash
# Install development environment
make install

# Start services with Docker
docker compose up -d

# Run tests
make tests

# Auto-fix formatting
make chores
```

See the [developer documentation](./docs/dev/README.md) for complete guides and reference.

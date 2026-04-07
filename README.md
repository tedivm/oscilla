# oscilla

## Installation

```bash
pip install oscilla
```

## Playing Locally

Oscilla requires a game library — a directory of game packages, each containing YAML manifests that define the game world. By default it looks for a `content/` directory in the project root. You can point it at any game library with the `GAMES_PATH` environment variable.

```bash
# Validate all game packages before playing
uv run oscilla validate

# Start an interactive game session (choose a game from the TUI if multiple are present)
uv run oscilla game

# Jump straight into a specific game by name
uv run oscilla game --game the-kingdom

# Use a custom game library directory
GAMES_PATH=/path/to/my-library uv run oscilla game
```

## Game Library Layout

The game library root must contain one or more game package subdirectories. Each game package directory must contain a `game.yaml` to be loaded.

```
content/             ← GAMES_PATH (game library root)
  the-kingdom/       ← game package
    game.yaml
    character_config.yaml
    regions/
  testlandia/        ← game package
    game.yaml
    character_config.yaml
    regions/
```

## CLI

All commands are available via `oscilla`. Run any command with `--help` for full usage.

```bash
uv run oscilla --help
```

### `game` — Play

Launches the interactive terminal UI. The game resolves your user identity from the system environment, then presents a game-selection screen when multiple games are present. After selecting a game, you can select or create a character.

```bash
uv run oscilla game
```

| Option                  | Short          | Description                                                                                      |
| ----------------------- | -------------- | ------------------------------------------------------------------------------------------------ |
| `--game GAME_NAME`      | `-g GAME_NAME` | Load this game directly by its manifest name, skipping the selection screen.                     |
| `--character-name NAME` | `-c NAME`      | Load or create the character with this name, skipping the selection screen.                      |
| `--reset-db`            |                | Delete all saved characters for the **selected game** before starting. Prompts for confirmation. |

**Examples**

```bash
# Jump straight into a named character in a specific game
uv run oscilla game --game the-kingdom --character-name "Aldric"

# Wipe your save data for a game and start fresh
uv run oscilla game --game the-kingdom --reset-db

# Combine: reset, then immediately start a named character
uv run oscilla game --game the-kingdom --reset-db --character-name "Aldric"
```

> **Note:** `--reset-db` permanently deletes all characters associated with your user **for the selected game only**. The CLI will ask for confirmation before proceeding, naming the specific game.

### `validate` — Check Content

Loads and validates all game packages in the library, printing a per-game summary on success or a list of errors on failure. Exits with code 1 if any errors are found.

```bash
# Validate all game packages
uv run oscilla validate

# Validate a specific game package
uv run oscilla validate --game testlandia
```

### `version` — Show Version

Prints the installed version of Oscilla.

```bash
uv run oscilla version
```

### `data-path` — Show Data Directory

Prints the platform data directory where Oscilla stores its database, log file, and crash reports. Useful for backup, reset, or inspection scripts.

```bash
uv run oscilla data-path
```

**Example** (macOS):

```
/Users/alice/Library/Application Support/oscilla
```

Use it in shell pipelines to work with the files directly:

```bash
# List all files in the data directory
ls $(uv run oscilla data-path)

# Back up the database
cp $(uv run oscilla data-path)/oscilla.db ~/Desktop/oscilla-backup.db
```

### Environment Variables

| Variable       | Default                                        | Description                                                                                                                              |
| -------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `GAMES_PATH`   | `content/`                                     | Path to the game library root directory. Each immediate subdirectory with a `game.yaml` is treated as a game package.                    |
| `DATABASE_URL` | auto-derived: `<platform data dir>/oscilla.db` | SQLAlchemy async database URL for character persistence. See [docs/dev/database.md](./docs/dev/database.md) for the per-OS default path. |

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

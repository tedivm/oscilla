## MODIFIED Requirements

### Requirement: Content directory scanning

The content loader SHALL accept a configurable game *library root* path via the `GAMES_PATH` setting (env var `GAMES_PATH`). The `load_games(library_root: Path)` function SHALL scan immediate subdirectories of `library_root` for game packages (directories containing a `game.yaml`). Subdirectories without a `game.yaml` are silently skipped. The single-game `load(content_dir: Path)` function is retained as an internal helper. The `CONTENT_PATH` / `content_path` setting is removed.

#### Scenario: GAMES_PATH is used as library root

- **WHEN** the `GAMES_PATH` setting is set to a custom directory
- **THEN** `load_games()` scans that directory's immediate subdirectories for game packages

#### Scenario: Non-YAML files are ignored within a game package

- **WHEN** a game package directory contains files with extensions other than `.yaml` or `.yml`
- **THEN** those files are silently ignored during manifest scanning

#### Scenario: Game package with no YAML files loads cleanly

- **WHEN** a subdirectory contains a `game.yaml` but no other manifests
- **THEN** the package loads without error and the registry contains only the `Game` manifest

---

### Requirement: Validate CLI command

The system SHALL provide a `validate` CLI command that loads and validates all game packages under `GAMES_PATH`. By default it validates all games and reports errors per-game. An optional `--game GAME_NAME` flag restricts validation to a single named game package.

#### Scenario: Validate with no flag validates all games

- **WHEN** `oscilla validate` is run against a library root containing two game packages
- **THEN** both packages are validated and a per-game success or error summary is printed

#### Scenario: Validate with --game validates one game

- **WHEN** `oscilla validate --game testlandia` is run
- **THEN** only the `testlandia` package is validated; other packages are not loaded

#### Scenario: Valid content reports success per game

- **WHEN** `oscilla validate` is run against a library where all packages have no errors
- **THEN** the command exits with code 0 and prints a success summary for each game

#### Scenario: Invalid content reports all errors

- **WHEN** `oscilla validate` is run and one game contains an invalid manifest
- **THEN** the command exits with a non-zero code and prints each error with its game package name and source file path

#### Scenario: Validate does not start the game

- **WHEN** `oscilla validate` completes (success or failure)
- **THEN** no game session is started and no player state is initialized

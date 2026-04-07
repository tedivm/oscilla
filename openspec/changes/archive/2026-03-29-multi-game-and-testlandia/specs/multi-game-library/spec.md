## ADDED Requirements

### Requirement: Game library root structure

The `GAMES_PATH` setting SHALL point to a _game library root_ — a directory whose immediate subdirectories are individual game packages. Each game package SHALL contain at minimum a `game.yaml` manifest. Subdirectories that do not contain a `game.yaml` SHALL be silently skipped.

#### Scenario: Library root contains two valid game packages

- **WHEN** `GAMES_PATH` points to a directory with two subdirectories each containing a valid `game.yaml`
- **THEN** `load_games()` returns a dict with two entries keyed by each `game.yaml`'s `metadata.name`

#### Scenario: Subdirectory without game.yaml is skipped

- **WHEN** the library root contains a subdirectory with YAML files but no `game.yaml`
- **THEN** that subdirectory is silently ignored and does not appear in the returned dict

#### Scenario: Empty library root returns empty dict

- **WHEN** `GAMES_PATH` points to a directory with no subdirectories containing `game.yaml`
- **THEN** `load_games()` returns an empty dict

---

### Requirement: load_games() public API

The engine SHALL expose a `load_games(library_root: Path) -> Dict[str, ContentRegistry]` function that scans the library root, calls `load()` for each game package subdirectory that contains a `game.yaml`, and returns the results keyed by `metadata.name` from each game's `game.yaml`. Errors within a single game package SHALL be collected and raised as a `ContentLoadError` that identifies the game package by name.

#### Scenario: Valid multi-game library loads all games

- **WHEN** `load_games()` is called on a library root with two valid game packages
- **THEN** both `ContentRegistry` objects are returned and each contains the manifests from its own package only

#### Scenario: Error in one game package is reported

- **WHEN** one game package contains a manifest with a broken cross-reference
- **THEN** `ContentLoadError` is raised, identifying the game package name and the specific error

---

### Requirement: GAMES_PATH setting replaces CONTENT_PATH

The `games_path` setting (env var `GAMES_PATH`) SHALL point to the game library root. The old `content_path` / `CONTENT_PATH` setting SHALL be removed. The default SHALL resolve to the `content/` directory at the project root.

#### Scenario: GAMES_PATH env var is respected

- **WHEN** `GAMES_PATH=/my/games` is set in the environment
- **THEN** the engine loads games from `/my/games/` subdirectories

#### Scenario: CONTENT_PATH env var is not recognised

- **WHEN** `CONTENT_PATH=/old/path` is set but `GAMES_PATH` is not
- **THEN** the engine uses its default `GAMES_PATH` value and does not attempt to load from `CONTENT_PATH`

---

### Requirement: Game-selection TUI screen

When `oscilla game` is run without a `--game` flag and the library contains more than one game, the engine SHALL display a game-selection screen before character selection. The screen SHALL show each game's `spec.displayName` and `spec.description`. Selecting a game proceeds to character selection for that game. When only one game is present, the selection screen SHALL be skipped.

#### Scenario: Multiple games triggers selection screen

- **WHEN** `oscilla game` is run with two games loaded and no `--game` flag
- **THEN** a game-selection screen is shown listing both games by display name

#### Scenario: Single game skips selection screen

- **WHEN** `oscilla game` is run with exactly one game loaded
- **THEN** that game is selected automatically and the character-selection screen is shown immediately

#### Scenario: --game flag bypasses selection screen

- **WHEN** `oscilla game --game testlandia` is run
- **THEN** Testlandia is selected without showing the selection screen

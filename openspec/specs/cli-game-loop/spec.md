# CLI Game Loop

## Purpose

The CLI game loop provides the interactive terminal user interface for the game, handling menus, player input, and adventure progression.

## Requirements

### Requirement: Game launch command

The system SHALL provide a `game` CLI command that resolves the user's TUI identity, optionally selects a game, performs character selection or creation, and launches the menu-driven TUI game loop backed by a `GameSession`. The command SHALL accept:

- `--game GAME_NAME` (string, optional): selects the game package by `metadata.name`, skipping the game-selection screen.
- `--character-name NAME` (string, optional): names the character to load or create, scoped to the selected game.
- `--reset-db` (flag, optional): deletes all characters for the current user in the **selected game only**, with confirmation, before starting.

#### Scenario: Game starts with character creation on first launch

- **WHEN** `oscilla game` is run for the first time (no existing characters for this user in the selected game)
- **THEN** the user is prompted to enter a character name, a new character is created and saved to the database, and the game loop begins

#### Scenario: Game auto-loads single existing character

- **WHEN** `oscilla game` is run and the user has exactly one saved character in the selected game
- **THEN** that character is loaded from the database and the game loop begins without prompting for a name

#### Scenario: Game shows character selection when multiple characters exist

- **WHEN** `oscilla game` is run and the user has two or more saved characters in the selected game
- **THEN** a character selection menu is displayed; the user chooses a character or selects `[+] New Character`

#### Scenario: Game state is saved across sessions

- **WHEN** the user exits the game after completing an adventure
- **THEN** the character's state as of the last `adventure_end` checkpoint is available when the game is next launched

#### Scenario: --character-name loads named character

- **WHEN** `oscilla game --character-name "Aragorn"` is run and "Aragorn" exists for the current user in the selected game
- **THEN** "Aragorn" is loaded from the database without showing the selection menu

#### Scenario: --character-name creates new character

- **WHEN** `oscilla game --character-name "Legolas"` is run and no character named "Legolas" exists in the selected game
- **THEN** a new character named "Legolas" is created and saved immediately

#### Scenario: --game selects a game without showing the selection screen

- **WHEN** `oscilla game --game testlandia` is run with multiple games loaded
- **THEN** Testlandia is selected immediately and the character-selection screen is shown without a game-selection step

#### Scenario: --reset-db is scoped to the selected game

- **WHEN** `oscilla game --reset-db --game testlandia` is confirmed by the user
- **THEN** only Testlandia characters for the current user are deleted; The Kingdom characters are unaffected

---

### Requirement: Adventure selection and execution

After selecting a location, the engine SHALL randomly select one adventure from the location's adventure pool, filtered to those whose conditions are met by the current player state and weighted by the `weight` field. The selected adventure SHALL then be executed via the adventure pipeline.

#### Scenario: Adventure is randomly selected from pool

- **WHEN** a location has three available adventures with weights 50, 30, 20
- **THEN** one is selected at random according to those weights and executed

#### Scenario: Unavailable adventures excluded from pool

- **WHEN** a location has adventures and one has a `requires` condition not met by the player
- **THEN** that adventure is excluded from the selection pool

#### Scenario: No available adventures at location

- **WHEN** all adventures at a location have unmet conditions
- **THEN** the player is notified that nothing is happening here and returned to location selection

---

### Requirement: In-adventure TUI interaction

During adventure execution, the TUI SHALL render each step appropriately: displaying narrative text in the scrollable narrative log, combat as a turn-by-turn exchange with HP information, and choice steps as arrow-key navigable menus in the choice widget. Player input SHALL be collected via arrow-key selection and Enter confirmation. Number-entry menus SHALL NOT be used.

#### Scenario: Narrative step is displayed

- **WHEN** a narrative step executes
- **THEN** the step text is appended to the narrative log and a "Continue" prompt is shown in the choice widget; the game loop pauses until the player presses Enter

#### Scenario: Combat turn is displayed

- **WHEN** a combat round executes
- **THEN** both the player and enemy HP are shown in the narrative log, the player selects an action via the arrow-key choice menu, the player's action resolves, the enemy's action resolves, and the outcome of the round is reflected in the status sidebar

#### Scenario: Choice step presents menu

- **WHEN** a choice step executes with three valid options
- **THEN** an arrow-key navigable list of those options is shown in the choice widget and the player selects by navigating and pressing Enter

---

### Requirement: Player status display

The TUI SHALL display a persistent player status sidebar showing: player name, level, XP, HP/max_HP, and all stats declared under `public_stats` in the `CharacterConfig` manifest. Hidden stats are never shown. The sidebar SHALL be updated automatically before each new display event — explicit "show status" calls at loop iteration boundaries are not required because the sidebar is always visible.

#### Scenario: Status reflects current values after adventure

- **WHEN** an adventure completes (any outcome)
- **THEN** the updated player status (including any XP/item/milestone changes) is immediately visible in the persistent sidebar before the next menu is presented

---

### Requirement: data-path command is available in the CLI

The system SHALL expose a `data-path` command in the `oscilla` CLI that prints the resolved user data directory to stdout. This is defined here as a CLI-loop concern: it is a first-class, discoverable CLI command alongside `game`, `validate`, and `version`.

#### Scenario: data-path appears in --help output

- **WHEN** `oscilla --help` is run
- **THEN** `data-path` appears in the list of available commands with a brief description

#### Scenario: data-path is a synchronous command

- **WHEN** `data-path` is invoked
- **THEN** it completes without requiring an async runtime, database connection, or any external service

---

### Requirement: Validate command options

The `oscilla validate` command SHALL accept the following flags:

- `--game GAME_NAME` (string, optional): validate only this game package. Silently ignored when `--stdin` is used.
- `--stdin` (flag, optional): read YAML manifest content from stdin instead of from GAMES_PATH.
- `--strict` (flag, optional): treat warnings as errors and exit 1 if any are present.
- `--no-semantic` (flag, optional): skip semantic checks (undefined refs, circular chains, orphaned/unreachable content).
- `--no-references` (flag, optional): skip cross-manifest reference validation.
- `--format FORMAT` (string, optional, default `text`): output format — `text`, `json`, or `yaml`.

#### Scenario: --format flag appears in validate --help

- **WHEN** `oscilla validate --help` is run
- **THEN** `--format` and `-F` appear in the output

#### Scenario: --no-references flag appears in validate --help

- **WHEN** `oscilla validate --help` is run
- **THEN** `--no-references` appears in the output

#### Scenario: validate with no flags uses text output

- **WHEN** `oscilla validate` is run with no flags
- **THEN** output is in text format (no JSON structure)

---

### Requirement: content test command is a backwards-compatible alias

The `oscilla content test` command SHALL remain available and SHALL behave identically to `oscilla validate` for disk-based validation. It SHALL accept `--game`, `--strict`, and `--format` flags with the same semantics. It SHALL NOT accept `--no-references` or `--no-semantic`.

#### Scenario: content test succeeds on valid content

- **WHEN** `oscilla content test` is run against valid game content
- **THEN** the command exits 0

#### Scenario: content test --format json produces structured output

- **WHEN** `oscilla content test --format json` is run
- **THEN** stdout is valid JSON containing `errors`, `warnings`, and `summary` keys

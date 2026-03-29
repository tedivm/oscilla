# CLI Game Loop

## Purpose

The CLI game loop provides the interactive terminal user interface for the game, handling menus, player input, and adventure progression.

## Requirements

### Requirement: Game launch command

The system SHALL provide a `game` CLI command that resolves the user's TUI identity, performs character selection or creation, and launches the menu-driven TUI game loop backed by a `GameSession`. The command SHALL accept a `--character-name` option (string, optional) that names the character to load or create.

#### Scenario: Game starts with character creation on first launch

- **WHEN** `oscilla game` is run for the first time (no existing characters for this user)
- **THEN** the user is prompted to enter a character name, a new character is created and saved to the database, and the game loop begins

#### Scenario: Game auto-loads single existing character

- **WHEN** `oscilla game` is run and the user has exactly one saved character
- **THEN** that character is loaded from the database and the game loop begins without prompting for a name

#### Scenario: Game shows character selection when multiple characters exist

- **WHEN** `oscilla game` is run and the user has two or more saved characters
- **THEN** a character selection menu is displayed; the user chooses a character or selects `[+] New Character`

#### Scenario: Game state is saved across sessions

- **WHEN** the user exits the game (via the quit option or Ctrl-C) after completing an adventure
- **THEN** the character's state as of the last `adventure_end` checkpoint is available when the game is next launched

#### Scenario: --character-name loads named character

- **WHEN** `oscilla game --character-name "Aragorn"` is run and "Aragorn" exists for the current user
- **THEN** "Aragorn" is loaded from the database without showing the selection menu

#### Scenario: --character-name creates new character

- **WHEN** `oscilla game --character-name "Legolas"` is run and no character named "Legolas" exists
- **THEN** a new character named "Legolas" is created and saved immediately

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


## MODIFIED Requirements

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

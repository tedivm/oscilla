## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Game session is lost on exit

**Reason**: Persistence is now implemented. Character state is saved to the database after each adventure and on mid-adventure checkpoints. The concept of a session being "lost on exit" no longer applies.

**Migration**: No user-facing migration needed. Existing saves (if any) are unaffected; new saves are created automatically.

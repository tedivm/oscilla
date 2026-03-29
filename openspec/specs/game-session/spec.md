# Game Session

## Purpose

Defines the `GameSession` orchestrator that ties content loading, user identity, character state, database persistence, and adventure pipeline execution together for the TUI game loop.

## Requirements

### Requirement: GameSession owns the TUI runtime lifecycle

`GameSession` (`oscilla/engine/session.py`) SHALL be the single entry point for the TUI game loop. It SHALL hold references to:

- `ContentRegistry` — loaded once at session start
- `CharacterState` — the currently active character
- `AsyncSession` — the database session
- `TUICallbacks` — the TUI protocol implementation

On `start()`, it SHALL resolve user identity, run character selection or creation, and prepare the character state for the game loop.

#### Scenario: Session start loads content and resolves user

- **WHEN** `GameSession.start()` is called
- **THEN** the content registry is loaded, the TUI user key is derived, the user is looked up or created in the DB, and character selection proceeds

---

### Requirement: Character selection on startup

On startup, `GameSession.start()` SHALL query all `CharacterRecord` rows belonging to the resolved user, ordered by `updated_at DESC`, and:

- **0 characters** → call `_create_new_character()` to create a new `CharacterState` and save it immediately
- **1 character** → auto-load that character, no prompt shown
- **N characters (N > 1)** → present a character selection menu via `TUICallbacks`; the menu SHALL always include a `[+] New Character` option at the bottom

#### Scenario: No existing characters

- **WHEN** the user has no saved characters
- **THEN** a new character creation flow begins without showing a selection menu

#### Scenario: One existing character

- **WHEN** the user has exactly one saved character
- **THEN** that character is loaded automatically and no selection menu is shown

#### Scenario: Multiple existing characters

- **WHEN** the user has two or more saved characters
- **THEN** a selection menu is shown with each character name, level, class, and last played date, plus a `[+] New Character` option

#### Scenario: User selects New Character from menu

- **WHEN** the user selects `[+] New Character` from the character selection menu
- **THEN** the new character creation flow begins

---

### Requirement: New character creation saves immediately

When a new character is created, `GameSession._create_new_character()` SHALL:

1. Apply the `--character-name` CLI argument as the character name if provided
2. Otherwise prompt the user for a name via `TUICallbacks`
3. Initialize a `CharacterState` via `CharacterState.new_character()`
4. Save the record to DB immediately (with `character_class = None`, `current_location = None`)
5. Proceed to class and location selection before adventure is available

#### Scenario: New character with CLI name

- **WHEN** `--character-name "Aragorn"` is passed and no character named "Aragorn" exists
- **THEN** a new character named "Aragorn" is created without prompting for a name

#### Scenario: New character with prompted name

- **WHEN** no `--character-name` flag is given
- **THEN** the user is prompted to enter a name before character creation proceeds

---

### Requirement: GameSession implements PersistCallback

`GameSession` SHALL implement the `PersistCallback` protocol. It SHALL save the current `CharacterState` to the database on every call to `_on_state_change(state, event)`. The implementation SHALL handle `StaleDataError` by reloading the character from DB before retrying the save once.

#### Scenario: State saved on each pipeline event

- **WHEN** the adventure pipeline fires `step_start`, `combat_round`, or `adventure_end`
- **THEN** the `GameSession._on_state_change()` method persists the updated `CharacterState` to the database

#### Scenario: StaleDataError triggers reload and retry

- **WHEN** `_on_state_change()` encounters a `StaleDataError`
- **THEN** the character is reloaded from the database, the new in-memory state is applied, and the save is retried once

---

### Requirement: --character-name CLI flag filters character selection

The `oscilla game` CLI command SHALL accept a `--character-name` option. When provided:

- If a character with that name exists for the current user → that character is auto-loaded (skipping selection menu)
- If no character with that name exists → a new character with that name is created

#### Scenario: Named character exists

- **WHEN** `oscilla game --character-name "Aragorn"` is run and "Aragorn" exists
- **THEN** "Aragorn" is loaded without showing the character selection menu

#### Scenario: Named character does not exist

- **WHEN** `oscilla game --character-name "Legolas"` is run and "Legolas" does not exist
- **THEN** a new character named "Legolas" is created

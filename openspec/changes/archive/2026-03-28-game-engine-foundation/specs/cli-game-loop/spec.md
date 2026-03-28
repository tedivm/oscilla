## ADDED Requirements

### Requirement: Game launch command

The system SHALL provide a `game` CLI command that starts a new in-memory player session and launches the menu-driven TUI game loop.

#### Scenario: Game starts with character creation

- **WHEN** `oscilla game` is run
- **THEN** the player is prompted to enter a character name before the game loop begins

#### Scenario: Game session is lost on exit

- **WHEN** the player exits the game (via the quit option or Ctrl-C)
- **THEN** all player state is discarded (no persistence in this phase)

---

### Requirement: Region and location selection menus

The TUI game loop SHALL present a menu of accessible regions. After selecting a region, it SHALL present a menu of accessible locations within that region. Accessibility is determined by the condition evaluator applied to the current player state. Inaccessible regions and locations SHALL NOT appear in the menus.

#### Scenario: Only accessible regions shown

- **WHEN** the player is at the world map and two regions are accessible and one requires level 5 (player is level 2)
- **THEN** only the two accessible regions appear in the menu

#### Scenario: Only accessible locations shown

- **WHEN** a region is selected and some of its locations have unmet unlock conditions
- **THEN** only locations with met conditions appear in the location menu

#### Scenario: Region with no accessible locations shows notice

- **WHEN** all locations in a region have unmet conditions and the player selects that region
- **THEN** the player sees a notice that no locations are accessible and is returned to the region selection menu

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

During adventure execution, the TUI SHALL render each step appropriately: displaying narrative text as formatted panels, combat as a turn-by-turn exchange with HP bars, and choice steps as numbered menus. Player input SHALL be collected via menu selection (no free-text input required).

#### Scenario: Narrative step is displayed

- **WHEN** a narrative step executes
- **THEN** the step text is rendered in the terminal and a "Continue" prompt is shown

#### Scenario: Combat turn is displayed

- **WHEN** a combat round executes
- **THEN** both the player and enemy HP are shown, the player's action is resolved, the enemy's action is resolved, and the outcome of the round is displayed

#### Scenario: Choice step presents menu

- **WHEN** a choice step executes with three valid options
- **THEN** a numbered menu of those options is shown and the player selects by number

---

### Requirement: Player status display

The TUI SHALL display a persistent or on-demand player status panel showing: player name, level, XP, HP/max_HP, and all stats declared under `public_stats` in the `CharacterConfig` manifest. Hidden stats are never shown to the player. The status panel SHALL be shown at the top of each game loop iteration (before the region selection menu) and again immediately after each adventure outcome is displayed.

#### Scenario: Status shown after adventure

- **WHEN** an adventure completes (any outcome)
- **THEN** the updated player status (including any XP/item/milestone changes) is displayed before returning to location selection

---

### Requirement: Quit option

The TUI game loop SHALL always offer a quit option at the region/location selection menus. Selecting quit SHALL exit the game cleanly.

#### Scenario: Player quits from location menu

- **WHEN** the player selects the quit option at any menu level
- **THEN** the game exits cleanly with a farewell message

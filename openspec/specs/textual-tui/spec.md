# Textual TUI

## Purpose

The Textual TUI provides a full-screen, keyboard-driven terminal user interface for the game, built on the Textual framework. It implements the `TUICallbacks` async protocol and hosts the game loop as an async worker coroutine.

## Requirements

### Requirement: Full-screen Textual application layout

The game SHALL be presented as a full-screen Textual application with a persistent two-column layout: a left panel containing the narrative log and choice menu, and a right panel containing the player status and region context panels. The layout SHALL be maintained at all times during a game session.

#### Scenario: Layout is visible on launch

- **WHEN** the player launches `oscilla game`
- **THEN** the full-screen Textual app renders with the left narrative/choice area and the right status/region sidebar visible before any game content is shown

#### Scenario: Right sidebar persists during narrative

- **WHEN** a narrative step is displaying text in the left panel
- **THEN** the player status and region panels on the right remain visible and current

---

### Requirement: Persistent player status sidebar

The right panel SHALL contain a `StatusPanel` widget displaying the player's name, level, HP (current / max), XP (current / next threshold), and all stats declared under `public_stats` in the `CharacterConfig` manifest. The panel SHALL be refreshed before each new display event so it always reflects the current `PlayerState`. Hidden stats SHALL NOT appear.

#### Scenario: Status reflects current values

- **WHEN** the player gains XP from completing an adventure
- **THEN** the status sidebar shows the updated XP value before the next menu is presented to the player

#### Scenario: Hidden stats are not shown

- **WHEN** a stat is declared under `hidden_stats` in `CharacterConfig`
- **THEN** that stat does not appear anywhere in the status sidebar

---

### Requirement: Region context panel

The right panel SHALL contain a `RegionPanel` widget displaying the name and description of the currently active region. The panel SHALL be updated each time the player navigates to a new region. When no region has been selected yet (e.g., at the world map menu), the panel SHALL indicate that no region is selected.

#### Scenario: Region panel updates on navigation

- **WHEN** the player selects "The Kingdom" from the region menu
- **THEN** the region panel immediately shows "The Kingdom" and its description before the location menu is displayed

#### Scenario: Region panel at launch

- **WHEN** the game has just started and no region has been chosen
- **THEN** the region panel shows a placeholder or blank state

---

### Requirement: Scrollable narrative log

The left panel SHALL contain a scrollable `NarrativeLog` widget that accumulates all narrative text displayed during the session. Each `show_text()` call SHALL append a formatted entry to the log. Earlier entries SHALL remain visible by scrolling up. The log SHALL automatically scroll to the bottom when new content is appended.

#### Scenario: Narrative history is retained

- **WHEN** the player has completed three narrative steps in a session
- **THEN** scrolling up in the narrative log shows all three entries

#### Scenario: New entries scroll into view

- **WHEN** a new narrative entry is appended
- **THEN** the log scrolls to show the new entry without requiring player action

---

### Requirement: Arrow-key choice menu

The left panel SHALL contain a `ChoiceMenu` widget that presents the current set of options as a list navigable with the up/down arrow keys. The currently highlighted option SHALL be visually distinct. Pressing Enter SHALL confirm the selection. The widget SHALL replace its items for each new menu call.

#### Scenario: Arrow keys change selection

- **WHEN** a menu with three options is displayed and the player presses the down arrow key once
- **THEN** the second option is highlighted

#### Scenario: Enter confirms selection

- **WHEN** the player highlights option 2 and presses Enter
- **THEN** the game loop receives index 2 as the selected choice

#### Scenario: Menu replaces previous

- **WHEN** a second menu is displayed after the first has resolved
- **THEN** the new options replace the old ones in the choice widget

---

### Requirement: Async TUICallbacks implementation

`TextualTUI` SHALL implement the `TUICallbacks` async protocol. Each method SHALL post the appropriate update to the Textual widget tree and then `await` an `asyncio.Event` that is set by the widget when the player has acknowledged or selected. The game loop worker SHALL resume only after the event fires.

#### Scenario: show_text suspends until acknowledged

- **WHEN** `await tui.show_text(text)` is called
- **THEN** the text is appended to the narrative log and the game loop pauses until the player presses Enter

#### Scenario: show_menu suspends until selected

- **WHEN** `await tui.show_menu(prompt, options)` is called
- **THEN** the options are shown in the choice widget and the game loop pauses until the player presses Enter on a selection

---

### Requirement: Game loop runs as async Textual worker

The adventure game loop (region selection → location selection → adventure execution) SHALL run as an async Textual worker coroutine started on app mount. The worker SHALL drive the `AdventurePipeline` using `await`. When the player quits, the worker SHALL be cancelled cleanly by Textual's worker lifecycle system.

#### Scenario: Game starts immediately on app mount

- **WHEN** `oscilla game` launches the Textual app
- **THEN** the character name prompt appears in the choice/narrative area without any additional player action

#### Scenario: Quit exits cleanly

- **WHEN** the player selects "Quit" from the region menu
- **THEN** the Textual app exits cleanly with no error output

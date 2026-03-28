## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Region and location selection menus (REPL form)

**Reason:** Region and location selection is now handled by the Textual game loop worker using the same `ChoiceMenu` widget as all other menus. The old numbered-menu REPL form (`_select_region` / `_select_location` as standalone `cli.py` helpers) no longer exists as a separate construct.
**Migration:** No migration needed — this is a breaking change to an application that has never been deployed. Region and location selection behaviour (accessible filtering, weighted adventure selection) is preserved; only the delivery mechanism changes.

### Requirement: Quit option (REPL form)

**Reason:** Quit is still supported but is now a menu option within the Textual choice widget, consistent with all other choices. The Textual app also responds to standard terminal exit signals (Ctrl-C / Ctrl-Q).
**Migration:** None required.

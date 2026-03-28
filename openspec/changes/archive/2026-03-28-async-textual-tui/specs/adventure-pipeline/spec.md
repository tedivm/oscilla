## MODIFIED Requirements

### Requirement: Adventures are ordered lists of typed steps

An adventure manifest SHALL define a `steps` list where each entry is a typed step object. The adventure pipeline runner SHALL execute steps in declared order asynchronously. Each step SHALL have a `type` discriminator field that determines which handler processes it. All step handlers and the pipeline runner itself SHALL be `async def` coroutines.

#### Scenario: Steps execute in order

- **WHEN** an adventure with three steps (narrative, combat, stat_check) is run
- **THEN** the narrative step executes first, then combat, then stat_check

#### Scenario: Unknown step type is rejected at load time

- **WHEN** the content loader parses an adventure manifest containing a step with an unrecognised `type`
- **THEN** it raises a validation error identifying the adventure and the invalid step type

---

### Requirement: Narrative step

A `narrative` step SHALL display a text body to the player and pause until the player acknowledges it (e.g., presses Enter). The `run_narrative` handler SHALL be an `async def` function that `await`s `tui.show_text()` and `tui.wait_for_ack()`.

#### Scenario: Narrative is shown and acknowledged

- **WHEN** a narrative step executes
- **THEN** the step's `text` field is displayed and the pipeline pauses until player acknowledgement before proceeding to the next step

---

### Requirement: Combat step (turn-based)

A `combat` step SHALL initiate a turn-based fight between the player and an enemy referenced by name from the registry. Each round the player acts first, then the enemy. Combat ends when either the player's or enemy's HP reaches zero, or the player successfully flees. The `run_combat` handler SHALL be an `async def` function that `await`s all `tui` calls.

#### Scenario: Player wins combat

- **WHEN** a combat step runs and the player reduces the enemy's HP to 0
- **THEN** the combat step is marked complete and the pipeline proceeds to the next step

#### Scenario: Enemy defeats player

- **WHEN** a combat step runs and the enemy reduces the player's HP to 0
- **THEN** the adventure ends immediately and the player is returned to location selection

#### Scenario: Player flees

- **WHEN** a combat step runs and the player chooses to flee
- **THEN** the combat step terminates and the adventure ends (remaining steps are skipped)

#### Scenario: Turn order

- **WHEN** a combat round begins
- **THEN** the player's attack resolves before the enemy's attack in that round

---

### Requirement: Choice step (branching)

A `choice` step SHALL present the player with a labeled menu of options. Each option SHALL have a display label and a nested `steps` list that executes when that option is chosen. Conditions on options are evaluated at step execution time; options whose conditions are not met SHALL be hidden. The `run_choice` handler SHALL be an `async def` function that `await`s `tui.show_menu()`.

#### Scenario: Player selects an option

- **WHEN** a choice step presents three options and the player selects option 2
- **THEN** the nested steps of option 2 execute and the pipeline continues with the step after the choice

#### Scenario: Option hidden by unmet condition

- **WHEN** a choice step has an option with a `requires` condition that the player does not meet
- **THEN** that option is not shown in the menu

#### Scenario: All options hidden

- **WHEN** all options in a choice step have unmet conditions
- **THEN** the step is skipped and the pipeline continues to the next step

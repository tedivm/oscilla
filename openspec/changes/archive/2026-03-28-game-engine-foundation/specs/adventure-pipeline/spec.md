## ADDED Requirements

### Requirement: Adventures are ordered lists of typed steps

An adventure manifest SHALL define a `steps` list where each entry is a typed step object. The adventure pipeline runner SHALL execute steps in declared order. Each step SHALL have a `type` discriminator field that determines which handler processes it.

#### Scenario: Steps execute in order

- **WHEN** an adventure with three steps (narrative, combat, stat_check) is run
- **THEN** the narrative step executes first, then combat, then stat_check

#### Scenario: Unknown step type is rejected at load time

- **WHEN** the content loader parses an adventure manifest containing a step with an unrecognised `type`
- **THEN** it raises a validation error identifying the adventure and the invalid step type

---

### Requirement: Narrative step

A `narrative` step SHALL display a text body to the player and pause until the player acknowledges it (e.g., presses a key or selects "Continue").

#### Scenario: Narrative is shown and acknowledged

- **WHEN** a narrative step executes
- **THEN** the step's `text` field is displayed and the pipeline pauses until player acknowledgement before proceeding to the next step

---

### Requirement: Combat step (turn-based)

A `combat` step SHALL initiate a turn-based fight between the player and an enemy referenced by name from the registry. Each round the player acts first, then the enemy. Combat ends when either the player's or enemy's HP reaches zero, or the player successfully flees. On player victory, the pipeline continues. On player defeat, the adventure ends and the player is returned to the location selection with reduced HP. On flee, the adventure ends without penalty beyond the used turn.

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

A `choice` step SHALL present the player with a labeled menu of options. Each option SHALL have a display label and a nested `steps` list that executes when that option is chosen. Conditions on options are evaluated at step execution time; options whose conditions are not met SHALL be hidden.

#### Scenario: Player selects an option

- **WHEN** a choice step presents three options and the player selects option 2
- **THEN** the nested steps of option 2 execute and the pipeline continues with the step after the choice

#### Scenario: Option hidden by unmet condition

- **WHEN** a choice step has an option with a `requires` condition that the player does not meet
- **THEN** that option is not shown in the menu

#### Scenario: All options hidden

- **WHEN** all options in a choice step have unmet conditions
- **THEN** the step is skipped and the pipeline continues to the next step

---

### Requirement: Item drop effect (loot)

An `item_drop` effect SHALL contain a weighted loot table of item references. The engine SHALL randomly select one item from the table (weighted by the `weight` field) and add one unit of that item to the player's inventory. The effect MAY have a `count` field specifying how many independent rolls to make (default 1). Effects are silent state mutations — no TUI output is produced.

#### Scenario: Item is granted to player

- **WHEN** an item_drop effect executes and the weighted roll selects `iron-sword`
- **THEN** one `iron-sword` is added to the player's inventory

#### Scenario: Multiple rolls

- **WHEN** an item_drop effect has `count: 3`
- **THEN** three independent weighted rolls are made and each resulting item is added to inventory

---

### Requirement: Milestone grant effect

A `milestone_grant` effect SHALL add a named milestone to the player's milestone set. If the player already has the milestone, the effect SHALL be a no-op. Effects are silent state mutations — no TUI output is produced.

#### Scenario: New milestone is granted

- **WHEN** a milestone_grant effect executes with `milestone: cleared-goblin-cave` and the player does not have that milestone
- **THEN** the milestone is added to the player's milestone set

#### Scenario: Duplicate milestone is no-op

- **WHEN** a milestone_grant effect executes with a milestone the player already has
- **THEN** the effect completes without error and the milestone set is unchanged

---

### Requirement: XP grant effect

An `xp_grant` effect SHALL add a specified amount of XP to the player. Negative amounts are valid (XP penalty). If the resulting total XP meets or exceeds the threshold for the next level, the player's level SHALL be incremented automatically and `max_hp` recalculated. Effects are silent state mutations — `add_xp()` returns the list of level numbers gained (empty if none) but no TUI output is produced at effect dispatch time. The updated level and HP are visible in `show_status()` after the adventure.

#### Scenario: XP is added without levelling

- **WHEN** an xp_grant effect grants 50 XP and the player does not have enough total XP to level up
- **THEN** the player's XP increases by 50 and level remains unchanged

#### Scenario: XP triggers level up

- **WHEN** an xp_grant effect grants enough XP to cross a level threshold
- **THEN** the player's level increments, `max_hp` is recalculated, and the new level is visible in the status display after the adventure completes

---

### Requirement: End adventure effect

An `end_adventure` effect SHALL immediately terminate the running adventure with a declared outcome (`completed`, `defeated`, or `fled`). It is useful for story branches where a narrative choice or a trap ends the run without combat. Effects that appear before `end_adventure` in the same effects list still fire; steps after the triggering branch are skipped.

#### Scenario: End adventure terminates adventure immediately

- **WHEN** an `end_adventure` effect with `outcome: defeated` fires inside a choice option's effects list
- **THEN** the adventure ends immediately with the `DEFEATED` outcome and remaining steps are not executed

#### Scenario: Effects before end_adventure still fire

- **WHEN** an effects list contains `[xp_grant, end_adventure]`
- **THEN** the XP is granted before the adventure terminates

---

### Requirement: goto and label for step navigation

Any top-level step in an adventure MAY carry a `label` string. An `OutcomeBranch` or `ChoiceOption` MAY specify a `goto` string instead of a `steps` list; when a `goto` fires, execution jumps to the first top-level step whose `label` matches. `goto` and `steps` are mutually exclusive within the same branch or option. Labels must be unique across all top-level steps in the adventure and are validated at load time.

#### Scenario: goto jumps to labeled step

- **WHEN** a combat step's `on_defeat` branch has `goto: shared-defeat` and a top-level step has `label: shared-defeat`
- **THEN** execution continues from the labeled step

#### Scenario: Duplicate label rejected at load time

- **WHEN** two top-level steps in the same adventure share the same `label` value
- **THEN** the content loader raises a validation error identifying the adventure and the duplicate label

#### Scenario: Unresolved goto rejected at load time

- **WHEN** a `goto` references a label that does not exist on any top-level step in that adventure
- **THEN** the content loader raises a validation error identifying the adventure and the missing label

---

### Requirement: Stat check step (conditional branch)

A `stat_check` step SHALL evaluate a condition against the current player state and execute one of two nested step lists: `on_pass` if the condition evaluates to true, or `on_fail` if false. Either branch may be empty.

#### Scenario: Passing branch executes

- **WHEN** a stat_check step evaluates its condition as true
- **THEN** the `on_pass` steps execute and the pipeline continues after the stat_check

#### Scenario: Failing branch executes

- **WHEN** a stat_check step evaluates its condition as false
- **THEN** the `on_fail` steps execute and the pipeline continues after the stat_check

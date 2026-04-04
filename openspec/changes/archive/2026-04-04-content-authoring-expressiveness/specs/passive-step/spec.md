## ADDED Requirements

### Requirement: Passive step applies effects automatically

A `passive` step type SHALL exist in the adventure step system. When executed, a passive step SHALL apply all listed `effects` in order using the same `run_effect` dispatcher used by all adventure effects. The player takes no action and makes no choice. The outcome of a passive step is always `completed`.

#### Scenario: Passive step applies all effects

- **WHEN** a passive step with `effects: [{type: stat_change, stat: hp, amount: -10}]` is executed
- **THEN** the player's HP is reduced by 10

#### Scenario: Passive step with no effects is valid

- **WHEN** a passive step is declared with an empty `effects` list
- **THEN** the step executes without error and the adventure continues

---

### Requirement: Passive step text is shown before effects

A passive step MAY declare a `text` field. When `text` is present, the TUI SHALL display it before applying any effects.

#### Scenario: Text is shown before damage

- **WHEN** a passive step has `text: "The dart trap fires!"` and `effects: [{type: stat_change, stat: hp, amount: -10}]`
- **THEN** the text is shown to the player BEFORE the stat change is applied

#### Scenario: Step with no text applies effects silently

- **WHEN** a passive step has no `text` field defined
- **THEN** effects are applied with no preceding narrative shown

---

### Requirement: Bypass condition skips normal text and effects

A passive step MAY declare a `bypass` condition. When `bypass` is set and evaluates to true for the current player state, the step's `text` and all `effects` SHALL be skipped entirely. The optional `bypass_text` field, if present, is shown to the player when bypass fires. If `bypass_text` is absent, the bypass is silent.

#### Scenario: Bypass condition met — bypass_text shown, effects skipped

- **WHEN** a passive step has `bypass: {type: character_stat, name: dexterity, gte: 12}` and `bypass_text: "Your reflexes save you."` and the player's dexterity is 14
- **THEN** the TUI shows "Your reflexes save you." and NO effects are applied

#### Scenario: Bypass condition met — silent skip when no bypass_text

- **WHEN** a passive step has `bypass: {type: character_stat, name: dexterity, gte: 12}` and no `bypass_text`, and the bypass condition is satisfied
- **THEN** no text is shown and no effects are applied

#### Scenario: Bypass condition not met — normal execution

- **WHEN** a passive step has a `bypass` condition that evaluates to false
- **THEN** the step's text (if any) is shown and all effects are applied normally

#### Scenario: No bypass condition — always executes

- **WHEN** a passive step has no `bypass` field
- **THEN** the step's text and effects always execute regardless of player state

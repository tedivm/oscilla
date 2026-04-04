# Adventure Outcome Definitions

## Purpose

Defines how game content can declare custom adventure outcome names beyond the three engine-internal outcomes, how those outcomes are validated at load time, and how per-outcome completion counts are tracked and persisted.

## Requirements

### Requirement: game.yaml can declare custom outcome names

A `GameSpec` MAY declare an `outcomes: List[str]` field listing custom adventure outcome names. These names supplement the three engine-internal outcomes (`completed`, `defeated`, `fled`). All five may then be used in `end_adventure` effects. If `outcomes` is absent or empty, only the three engine-internal names are valid in `end_adventure` effects for that game.

#### Scenario: Custom outcome name is valid after declaration

- **WHEN** `game.yaml` declares `outcomes: [discovered]` and an adventure uses `end_adventure: {outcome: discovered}`
- **THEN** the content loads without error

#### Scenario: Undeclared custom outcome is a load error

- **WHEN** `game.yaml` does not declare `outcomes: [banished]` and an adventure uses `end_adventure: {outcome: banished}`
- **THEN** the content loader raises a validation error identifying the adventure and outcome name

#### Scenario: Engine-internal outcomes are always valid without declaration

- **WHEN** `game.yaml` declares no `outcomes` field and an adventure uses `end_adventure: {outcome: fled}`
- **THEN** the content loads without error

---

### Requirement: end_adventure effect accepts any declared outcome string

The `end_adventure` effect's `outcome` field SHALL accept any `str` value. The content loader SHALL validate that the value is either one of the three engine-internal outcomes (`completed`, `defeated`, `fled`) OR is declared in `game.yaml` outcomes list. This validation is a load-time error, not a runtime error.

#### Scenario: Valid custom outcome terminates adventure

- **WHEN** an `end_adventure` effect with `outcome: discovered` is executed during an adventure, and `discovered` is declared in `game.yaml`
- **THEN** the adventure terminates and the outcome value `"discovered"` is returned to the session layer

---

### Requirement: Per-adventure per-outcome completion counts are tracked

The engine SHALL track how many times each adventure has been completed with each outcome, stored in `CharacterStatistics.adventure_outcome_counts` as `Dict[str, Dict[str, int]]`. When an adventure ends, both `adventures_completed[ref]` (total) and `adventure_outcome_counts[ref][outcome]` SHALL be incremented. Counts are per character iteration and reset on prestige.

#### Scenario: Outcome count is incremented on completion

- **WHEN** an adventure completes with outcome `"completed"`
- **THEN** `adventure_outcome_counts[adventure_ref]["completed"]` is incremented by 1

#### Scenario: Different outcomes are tracked independently

- **WHEN** an adventure is run three times — twice ending with `"completed"` and once with `"fled"`
- **THEN** `adventure_outcome_counts[ref]["completed"]` is 2 and `adventure_outcome_counts[ref]["fled"]` is 1

---

### Requirement: Outcome counts persist across sessions

`adventure_outcome_counts` SHALL be persisted to the database using the existing `character_iteration_statistics` table with `stat_type` values of the form `adventure_outcome:{outcome_name}` (e.g. `adventure_outcome:completed`). They SHALL be restored on character load.

#### Scenario: Outcome count survives session restart

- **WHEN** a player completes an adventure with outcome `"discovered"` and ends the session
- **THEN** on next session start, `adventure_outcome_counts[ref]["discovered"]` is 1

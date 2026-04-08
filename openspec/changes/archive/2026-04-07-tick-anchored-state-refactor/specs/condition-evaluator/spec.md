## ADDED Requirements

### Requirement: Milestone ticks elapsed predicate

The `milestone_ticks_elapsed` leaf predicate SHALL evaluate to True when the specified number of `internal_ticks` have elapsed since the named milestone was granted. It SHALL accept `gte` (minimum elapsed ticks) and/or `lte` (maximum elapsed ticks). At least one of `gte` or `lte` SHALL be specified; providing neither is a validation error.

If the named milestone has not been granted to the player, the condition SHALL evaluate to False regardless of comparator values.

`internal_ticks` is always used — this predicate is unaffected by `adjust_game_ticks` effects.

#### Scenario: Milestone not granted — condition is false

- **WHEN** `milestone_ticks_elapsed: {name: "veteran", gte: 0}` is evaluated and the player has no "veteran" milestone
- **THEN** it evaluates to false

#### Scenario: gte condition passes when enough ticks elapsed

- **WHEN** `milestone_ticks_elapsed: {name: "joined-guild", gte: 5}` is evaluated and "joined-guild" was granted at tick 10 and current `internal_ticks` is 16 (6 elapsed)
- **THEN** it evaluates to true

#### Scenario: gte condition fails when not enough ticks elapsed

- **WHEN** `milestone_ticks_elapsed: {name: "joined-guild", gte: 10}` is evaluated and only 3 ticks have elapsed since grant
- **THEN** it evaluates to false

#### Scenario: lte condition passes when elapsed is within range

- **WHEN** `milestone_ticks_elapsed: {name: "new-recruit", lte: 5}` is evaluated and 3 ticks have elapsed since grant
- **THEN** it evaluates to true

#### Scenario: lte condition fails when too many ticks elapsed

- **WHEN** `milestone_ticks_elapsed: {name: "new-recruit", lte: 5}` is evaluated and 10 ticks have elapsed since grant
- **THEN** it evaluates to false

#### Scenario: Both gte and lte define a window

- **WHEN** `milestone_ticks_elapsed: {name: "cursed", gte: 3, lte: 10}` is evaluated and 5 ticks have elapsed since grant
- **THEN** it evaluates to true

#### Scenario: Outside the window fails

- **WHEN** `milestone_ticks_elapsed: {name: "cursed", gte: 3, lte: 10}` is evaluated and 15 ticks have elapsed since grant
- **THEN** it evaluates to false

#### Scenario: Neither gte nor lte is a validation error

- **WHEN** `milestone_ticks_elapsed: {name: "test"}` is parsed (no gte or lte)
- **THEN** a Pydantic validation error is raised at load time

#### Scenario: milestone_ticks_elapsed inside all condition

- **WHEN** an `all` condition contains `milestone_ticks_elapsed: {name: "veteran", gte: 2}` and a `milestone: {name: "veteran"}` predicate, both satisfied
- **THEN** the `all` node evaluates to true

## ADDED Requirements

### Requirement: Calendar condition predicates compose with existing tree nodes

All eight new calendar predicates (`season_is`, `moon_phase_is`, `zodiac_is`, `chinese_zodiac_is`, `month_is`, `day_of_week_is`, `date_is`, `time_between`) SHALL be valid leaf node types within the existing `Condition` union and SHALL compose with `all`, `any`, and `not` branch nodes identically to all other leaf predicates.

#### Scenario: calendar predicate under all node

- **WHEN** an `all` condition contains a `season_is` predicate and a `milestone` predicate, both of which are satisfied
- **THEN** the `all` node evaluates to true

#### Scenario: calendar predicate negated under not node

- **WHEN** a `not` condition wraps a `month_is: 10` predicate and the current month is July
- **THEN** the `not` node evaluates to true

## MODIFIED Requirements

### Requirement: Empty condition is always true

The condition evaluator SHALL return `True` whenever the `condition` argument is `None`. This requirement is unchanged; this MODIFIED entry ensures the new calendar predicates do not affect the None-guard behavior.

#### Scenario: No unlock block is always accessible

- **WHEN** `evaluate(condition=None, player=player)` is called
- **THEN** it returns `True` regardless of the player's state or calendar state

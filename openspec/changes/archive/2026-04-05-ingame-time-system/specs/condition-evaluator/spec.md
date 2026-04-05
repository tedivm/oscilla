## ADDED Requirements

### Requirement: In-game time condition predicates compose with existing tree nodes

Three new in-game time condition predicates — `game_calendar_time_is`, `game_calendar_cycle_is`, and `game_calendar_era_is` — SHALL be valid leaf node types within the `Condition` union and SHALL compose with `all`, `any`, and `not` branch nodes identically to all other leaf predicates. Full specification of individual predicate semantics is in the `ingame-time-conditions` spec.

#### Scenario: game_calendar_time_is under all node

- **WHEN** an `all` condition contains `game_calendar_time_is: {gte: 10}` and a `milestone` predicate, both satisfied
- **THEN** the `all` node evaluates to `true`

#### Scenario: game_calendar_cycle_is negated under not node

- **WHEN** a `not` condition wraps `game_calendar_cycle_is: {cycle: season, value: Winter}` and the current season is `"Summer"`
- **THEN** the `not` node evaluates to `true`

#### Scenario: game_calendar_era_is inside any node

- **WHEN** an `any` condition contains two `game_calendar_era_is` predicates, only one of which is satisfied
- **THEN** the `any` node evaluates to `true`

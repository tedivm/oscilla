# In-Game Time Conditions

## Purpose

Defines the three new condition predicates that evaluate in-game time state: `game_calendar_time_is` (numeric comparison on tick counters), `game_calendar_cycle_is` (cycle label comparison), and `game_calendar_era_is` (era activation state).

## Requirements

### Requirement: game_calendar_time_is evaluates numeric tick counter comparisons

The `game_calendar_time_is` condition predicate SHALL perform a numeric comparison against either `internal_ticks` or `game_ticks` on the current character state. The predicate SHALL support the same numeric operators available in other numeric predicates: `gt`, `gte`, `lt`, `lte`, `eq`, and `mod`. At least one operator MUST be declared; the predicate SHALL fail at parse time if none is declared.

The `clock` field selects which counter to query:

- `"internal"` (default): queries `CharacterState.internal_ticks`
- `"game"`: queries `CharacterState.game_ticks`

When the game does not have a `time:` block configured, the condition SHALL evaluate to `false` and log a warning.

#### Scenario: gte comparison against internal_ticks succeeds when met

- **WHEN** `game_calendar_time_is: {clock: internal, gte: 40}` and `internal_ticks = 50`
- **THEN** the condition evaluates to `true`

#### Scenario: gte comparison against internal_ticks fails when not met

- **WHEN** `game_calendar_time_is: {clock: internal, gte: 40}` and `internal_ticks = 30`
- **THEN** the condition evaluates to `false`

#### Scenario: game clock is queried with clock: game

- **WHEN** `game_calendar_time_is: {clock: game, lt: 100}` and `game_ticks = 88` and `internal_ticks = 200`
- **THEN** the condition evaluates to `true` (queries game_ticks, not internal_ticks)

#### Scenario: mod operator tests periodicity

- **WHEN** `game_calendar_time_is: {clock: internal, mod: {divisor: 10, remainder: 0}}` and `internal_ticks = 50`
- **THEN** the condition evaluates to `true`

#### Scenario: Condition without time system returns false with warning

- **WHEN** `game_calendar_time_is: {clock: internal, gte: 1}` is evaluated without a configured time system
- **THEN** the condition evaluates to `false`
- **THEN** a warning is logged identifying the missing time system

#### Scenario: Condition with no comparator raises parse error

- **WHEN** a manifest declares `game_calendar_time_is: {clock: internal}` with no gt/gte/lt/lte/eq/mod field
- **THEN** content loading raises a `ContentLoadError` or Pydantic `ValidationError`

---

### Requirement: game_calendar_cycle_is evaluates the label of a named cycle

The `game_calendar_cycle_is` condition predicate SHALL test whether the current label of a named cycle (identified by `cycle` field, which MAY be a cycle name or alias) equals the string declared in the `value` field.

The `value` field SHALL be validated against declared cycle labels at semantic validation time: if `value` is not in the cycle's `labels` list, the validator SHALL raise a `ContentLoadError`.

When the named cycle is not found in the registry, the condition SHALL evaluate to `false` and log a warning.

#### Scenario: Condition matches when cycle label equals value

- **WHEN** `game_calendar_cycle_is: {cycle: season, value: Summer}` and the current season label is `"Summer"`
- **THEN** the condition evaluates to `true`

#### Scenario: Condition does not match when label differs

- **WHEN** `game_calendar_cycle_is: {cycle: season, value: Summer}` and the current season label is `"Winter"`
- **THEN** the condition evaluates to `false`

#### Scenario: Alias resolves correctly in cycle condition

- **WHEN** the root cycle `hour` has alias `ship_hour` and `game_calendar_cycle_is: {cycle: ship_hour, value: Dawn}` is evaluated at tick 0
- **THEN** the condition resolves against the root cycle and evaluates to `true` when the first label is `"Dawn"`

#### Scenario: Undefined cycle name returns false with warning

- **WHEN** `game_calendar_cycle_is: {cycle: nonexistent, value: Spring}` is evaluated
- **THEN** the condition evaluates to `false`
- **THEN** a warning is logged identifying the unknown cycle

#### Scenario: Invalid label value raises load error at semantic validation

- **WHEN** a manifest declares `game_calendar_cycle_is: {cycle: season, value: NotALabel}` and `season` has labels `[Spring, Summer, Autumn, Winter]`
- **THEN** the semantic validator raises a `ContentLoadError` at load time

---

### Requirement: game_calendar_era_is evaluates era activation state

The `game_calendar_era_is` condition predicate SHALL test whether a named era (identified by `era` field) is currently active or inactive. The `state` field selects which state to test: `"active"` (default) or `"inactive"`.

An era is **active** when its `start_condition` has fired (or it has no `start_condition`) and its `end_condition` has not yet fired (or it has no `end_condition`). An era is **inactive** otherwise. Both conditions use the latch model: each fires at most once per iteration and is never re-evaluated after firing.

When the named era is not found in the registry, the condition SHALL evaluate to `false` and log a warning.

#### Scenario: Active era is detected as active

- **WHEN** `game_calendar_era_is: {era: CE, state: active}` and the `CE` era has no `start_condition` (always active) or its `start_condition` has already fired
- **THEN** the condition evaluates to `true`

#### Scenario: Inactive check inverts the result

- **WHEN** `game_calendar_era_is: {era: CE, state: inactive}` and the `CE` era is currently active
- **THEN** the condition evaluates to `false`

#### Scenario: Condition-gated era is inactive before its start_condition fires

- **WHEN** era `new_age` has `start_condition: {type: game_calendar_time_is, clock: game, gte: 100}` and `game_ticks = 50`
- **THEN** `game_calendar_era_is: {era: new_age, state: active}` evaluates to `false`

#### Scenario: Condition-gated era becomes active once start_condition fires

- **WHEN** era `new_age` has `start_condition: {type: game_calendar_time_is, clock: game, gte: 100}` and `game_ticks = 150`
- **THEN** `game_calendar_era_is: {era: new_age, state: active}` evaluates to `true`

#### Scenario: Undefined era name returns false with warning

- **WHEN** `game_calendar_era_is: {era: nonexistent}` is evaluated
- **THEN** the condition evaluates to `false`
- **THEN** a warning is logged identifying the unknown era

---

### Requirement: In-game time conditions compose with existing condition tree nodes

All three in-game time condition predicates (`game_calendar_time_is`, `game_calendar_cycle_is`, `game_calendar_era_is`) SHALL be valid leaf node types within the existing `Condition` union and SHALL compose with `all`, `any`, and `not` branch nodes identically to all other leaf predicates.

#### Scenario: Time condition under all node

- **WHEN** an `all` condition contains `game_calendar_time_is: {gte: 10}` and a `milestone` predicate, both of which are satisfied
- **THEN** the `all` node evaluates to `true`

#### Scenario: Cycle condition negated under not node

- **WHEN** a `not` condition wraps `game_calendar_cycle_is: {cycle: season, value: Winter}` and the current season is `"Summer"`
- **THEN** the `not` node evaluates to `true`

#### Scenario: Era condition inside any node

- **WHEN** an `any` condition contains `game_calendar_era_is: {era: old_age, state: inactive}` and `game_calendar_era_is: {era: new_age, state: active}`, and only the second is satisfied
- **THEN** the `any` node evaluates to `true`

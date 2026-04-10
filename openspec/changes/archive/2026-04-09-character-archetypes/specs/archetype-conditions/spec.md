## ADDED Requirements

### Requirement: has_archetype condition predicate

The `has_archetype` leaf predicate SHALL evaluate to true when the player's `archetypes` set contains the specified name.

Fields:

- `type: "has_archetype"` (discriminator)
- `name` (string, required): archetype manifest name to check.

#### Scenario: has_archetype true when archetype is held

- **WHEN** a `has_archetype: {name: warrior}` predicate is evaluated for a player with `"warrior"` in `archetypes`
- **THEN** it evaluates to true

#### Scenario: has_archetype false when archetype is not held

- **WHEN** a `has_archetype: {name: mage}` predicate is evaluated for a player who does not hold `"mage"`
- **THEN** it evaluates to false

#### Scenario: has_archetype false for empty archetypes set

- **WHEN** a `has_archetype: {name: warrior}` predicate is evaluated for a player with no archetypes
- **THEN** it evaluates to false

---

### Requirement: has_all_archetypes condition predicate

The `has_all_archetypes` leaf predicate SHALL evaluate to true when the player's `archetypes` set contains every name in the provided list.

Fields:

- `type: "has_all_archetypes"` (discriminator)
- `names` (list of strings, required): archetype manifest names; all must be held.

#### Scenario: has_all_archetypes true when all are held

- **WHEN** a `has_all_archetypes: {names: [warrior, mage]}` predicate is evaluated for a player holding both `"warrior"` and `"mage"`
- **THEN** it evaluates to true

#### Scenario: has_all_archetypes false when only some are held

- **WHEN** a `has_all_archetypes: {names: [warrior, mage]}` predicate is evaluated for a player holding only `"warrior"`
- **THEN** it evaluates to false

---

### Requirement: has_any_archetypes condition predicate

The `has_any_archetypes` leaf predicate SHALL evaluate to true when the player's `archetypes` set contains at least one name from the provided list.

Fields:

- `type: "has_any_archetypes"` (discriminator)
- `names` (list of strings, required): archetype manifest names; at least one must be held.

#### Scenario: has_any_archetypes true when at least one is held

- **WHEN** a `has_any_archetypes: {names: [warrior, paladin]}` predicate is evaluated for a player holding `"paladin"` but not `"warrior"`
- **THEN** it evaluates to true

#### Scenario: has_any_archetypes false when none are held

- **WHEN** a `has_any_archetypes: {names: [warrior, paladin]}` predicate is evaluated for a player holding neither
- **THEN** it evaluates to false

---

### Requirement: archetype_count condition predicate

The `archetype_count` leaf predicate SHALL evaluate to true when the number of archetypes held by the player satisfies a numeric comparison. At least one comparator field (`gte`, `lte`, `eq`) MUST be supplied.

Fields:

- `type: "archetype_count"` (discriminator)
- `gte` (int, optional): evaluates true when count ≥ value.
- `lte` (int, optional): evaluates true when count ≤ value.
- `eq` (int, optional): evaluates true when count == value.

#### Scenario: archetype_count gte true when player holds enough archetypes

- **WHEN** an `archetype_count: {gte: 2}` predicate is evaluated for a player holding three archetypes
- **THEN** it evaluates to true

#### Scenario: archetype_count gte false when player holds too few

- **WHEN** an `archetype_count: {gte: 2}` predicate is evaluated for a player holding one archetype
- **THEN** it evaluates to false

#### Scenario: archetype_count eq true for exact match

- **WHEN** an `archetype_count: {eq: 0}` predicate is evaluated for a player with no archetypes
- **THEN** it evaluates to true

---

---

### Requirement: archetype_ticks_elapsed condition predicate

The `archetype_ticks_elapsed` leaf predicate SHALL evaluate to true when the number of `internal_ticks` elapsed since the named archetype was granted satisfies a numeric comparison. The elapsed ticks are computed as `player.internal_ticks - player.archetypes[name].tick`. If the named archetype is not held, the predicate SHALL evaluate to false regardless of comparator values. At least one of `gte` or `lte` MUST be supplied; providing neither is a validation error raised at parse time.

Fields:

- `type: "archetype_ticks_elapsed"` (discriminator)
- `name` (string, required): archetype manifest name to look up.
- `gte` (int, optional): evaluates true when elapsed ticks ≥ value.
- `lte` (int, optional): evaluates true when elapsed ticks ≤ value.

#### Scenario: archetype not held — condition is false

- **WHEN** `archetype_ticks_elapsed: {name: warrior, gte: 0}` is evaluated and the player does not hold `"warrior"`
- **THEN** it evaluates to false

#### Scenario: gte condition passes when enough ticks have elapsed

- **WHEN** `archetype_ticks_elapsed: {name: warrior, gte: 5}` is evaluated and `"warrior"` was granted at tick 10 and current `internal_ticks` is 16 (6 elapsed)
- **THEN** it evaluates to true

#### Scenario: gte condition fails when not enough ticks have elapsed

- **WHEN** `archetype_ticks_elapsed: {name: warrior, gte: 10}` is evaluated and only 3 ticks have elapsed since grant
- **THEN** it evaluates to false

#### Scenario: lte condition passes when elapsed is within range

- **WHEN** `archetype_ticks_elapsed: {name: initiate, lte: 5}` is evaluated and 3 ticks have elapsed since grant
- **THEN** it evaluates to true

#### Scenario: lte condition fails when too many ticks have elapsed

- **WHEN** `archetype_ticks_elapsed: {name: initiate, lte: 5}` is evaluated and 10 ticks have elapsed since grant
- **THEN** it evaluates to false

#### Scenario: gte and lte define a window — within range

- **WHEN** `archetype_ticks_elapsed: {name: cursed, gte: 3, lte: 10}` is evaluated and 5 ticks have elapsed since grant
- **THEN** it evaluates to true

#### Scenario: gte and lte define a window — outside range

- **WHEN** `archetype_ticks_elapsed: {name: cursed, gte: 3, lte: 10}` is evaluated and 15 ticks have elapsed since grant
- **THEN** it evaluates to false

#### Scenario: Neither gte nor lte is a validation error

- **WHEN** `archetype_ticks_elapsed: {name: warrior}` is parsed (no gte or lte)
- **THEN** a Pydantic validation error is raised at load time

---

### Requirement: Archetype condition predicates compose with not, all, any

All four archetype condition predicates SHALL be composable with the standard logical wrappers `not`, `all`, and `any`.

#### Scenario: not has_archetype inverts the result

- **WHEN** a `not: {type: has_archetype, name: mage}` condition is evaluated for a player who does not hold `"mage"`
- **THEN** it evaluates to true

#### Scenario: all with mixed archetype and non-archetype predicates

- **WHEN** an `all` condition contains `has_archetype: {name: warrior}` and `level: {gte: 5}` and both are true
- **THEN** the `all` node evaluates to true

# Condition Evaluator

## Purpose

The condition evaluator provides the foundational system for evaluating unlock conditions, implementing a recursive tree structure with logical operators and typed leaf predicates for content gating.

## Requirements

### Requirement: Logical condition tree structure

Conditions SHALL be expressible as a recursive tree of logical operators (`all`, `any`, `not`) with typed leaf predicates. An `all` node SHALL evaluate to true only when every child evaluates to true. An `any` node SHALL evaluate to true when at least one child evaluates to true. A `not` node SHALL have exactly one child and evaluate to true when that child evaluates to false.

#### Scenario: All conditions pass

- **WHEN** an `all` condition contains three leaf predicates that all evaluate to true for the current player state
- **THEN** the `all` node evaluates to true

#### Scenario: Any with one passing child

- **WHEN** an `any` condition contains three leaf predicates and exactly one evaluates to true
- **THEN** the `any` node evaluates to true

#### Scenario: Not negates a passing condition

- **WHEN** a `not` condition wraps a leaf predicate that evaluates to true
- **THEN** the `not` node evaluates to false

---

### Requirement: Level leaf predicate

The `level` leaf predicate SHALL accept an integer value and evaluate to true when the player's current level is greater than or equal to that value.

#### Scenario: Player meets level requirement

- **WHEN** a `level: 3` predicate is evaluated for a player at level 4
- **THEN** it evaluates to true

#### Scenario: Player does not meet level requirement

- **WHEN** a `level: 5` predicate is evaluated for a player at level 3
- **THEN** it evaluates to false

---

### Requirement: Milestone leaf predicate

The `milestone` leaf predicate SHALL accept a milestone name string and evaluate to true when that milestone has been granted to the player.

#### Scenario: Milestone is present

- **WHEN** a `milestone: found-the-map` predicate is evaluated for a player who has the `found-the-map` milestone
- **THEN** it evaluates to true

#### Scenario: Milestone is absent

- **WHEN** a `milestone: found-the-map` predicate is evaluated for a player who does not have that milestone
- **THEN** it evaluates to false

---

### Requirement: Item leaf predicate

The `item` leaf predicate SHALL accept an item reference name and evaluate to true when the player currently has at least one of that item in their inventory.

#### Scenario: Item is in inventory

- **WHEN** an `item: old-key` predicate is evaluated for a player who has the `old-key` item
- **THEN** it evaluates to true

#### Scenario: Item is not in inventory

- **WHEN** an `item: old-key` predicate is evaluated for a player whose inventory does not contain `old-key`
- **THEN** it evaluates to false

---

### Requirement: Character stat leaf predicate (`character_stat`)

The `character_stat` leaf predicate SHALL accept a CharacterConfig-defined stat name and a numeric comparison (`gte`, `lte`, `eq`) and evaluate to true when the player's value for that stat satisfies the comparison. Both `public_stats` and `hidden_stats` defined in `CharacterConfig` are valid targets.

#### Scenario: Stat meets threshold

- **WHEN** a `character_stat: {name: strength, gte: 50}` predicate is evaluated for a player with strength 60
- **THEN** it evaluates to true

#### Scenario: Stat does not meet threshold

- **WHEN** a `character_stat: {name: strength, gte: 50}` predicate is evaluated for a player with strength 30
- **THEN** it evaluates to false

---

### Requirement: Class leaf predicate (placeholder)

The `class` leaf predicate SHALL accept a class name string. In this phase it SHALL always evaluate to true (no-op). This allows content to reference class conditions without the engine enforcing them until classes are implemented.

#### Scenario: Class predicate always passes in v1

- **WHEN** a `class: warrior` predicate is evaluated for any player regardless of their class field
- **THEN** it evaluates to true

---

### Requirement: Prestige count leaf predicate

The `prestige_count` leaf predicate SHALL accept a numeric comparison (`gte`, `lte`, `eq`) and evaluate to true when the player's prestige count satisfies the comparison.

#### Scenario: Player has enough prestiges

- **WHEN** a `prestige_count: {gte: 1}` predicate is evaluated for a player with prestige_count 2
- **THEN** it evaluates to true

#### Scenario: Player has not prestiged

- **WHEN** a `prestige_count: {gte: 1}` predicate is evaluated for a player with prestige_count 0
- **THEN** it evaluates to false

---

### Requirement: Empty condition is always true

When an entity has no `unlock` block or an empty condition, the condition evaluator SHALL treat it as unconditionally satisfied.

#### Scenario: No unlock block is always accessible

- **WHEN** the condition evaluator is called with a None or empty condition
- **THEN** it returns true without inspecting player state

---

### Requirement: Enemies defeated leaf predicate (`enemies_defeated`)

The `enemies_defeated` leaf predicate SHALL accept an enemy manifest name and a numeric comparison (`gte`, `lte`, `eq`) and evaluate to true when `player.statistics.enemies_defeated[name]` satisfies the comparison. A missing key SHALL be treated as 0.

#### Scenario: Kill count meets threshold

- **WHEN** an `enemies_defeated: {name: goblin-scout, gte: 2}` predicate is evaluated for a player who has defeated goblin-scout 3 times
- **THEN** it evaluates to true

#### Scenario: Kill count below threshold

- **WHEN** an `enemies_defeated: {name: goblin-scout, gte: 2}` predicate is evaluated for a player who has defeated goblin-scout 1 time
- **THEN** it evaluates to false

#### Scenario: Enemy never encountered

- **WHEN** an `enemies_defeated: {name: goblin-scout, gte: 1}` predicate is evaluated for a player with no goblin-scout entries in statistics
- **THEN** it evaluates to false (missing key treated as 0)

---

### Requirement: Locations visited leaf predicate (`locations_visited`)

The `locations_visited` leaf predicate SHALL accept a location manifest name and a numeric comparison (`gte`, `lte`, `eq`) and evaluate to true when `player.statistics.locations_visited[name]` satisfies the comparison. A missing key SHALL be treated as 0.

#### Scenario: Visit count meets threshold

- **WHEN** a `locations_visited: {name: village-square, gte: 3}` predicate is evaluated for a player who has visited village-square 5 times
- **THEN** it evaluates to true

#### Scenario: Location never visited

- **WHEN** a `locations_visited: {name: village-square, gte: 1}` predicate is evaluated for a player with no village-square entry
- **THEN** it evaluates to false

---

### Requirement: Adventures completed leaf predicate (`adventures_completed`)

The `adventures_completed` leaf predicate SHALL accept an adventure manifest name and a numeric comparison (`gte`, `lte`, `eq`) and evaluate to true when `player.statistics.adventures_completed[name]` satisfies the comparison. A missing key SHALL be treated as 0.

#### Scenario: Completion count meets threshold

- **WHEN** an `adventures_completed: {name: goblin-ambush, gte: 5}` predicate is evaluated for a player who has completed goblin-ambush 7 times
- **THEN** it evaluates to true

#### Scenario: Adventure never completed

- **WHEN** an `adventures_completed: {name: goblin-ambush, gte: 1}` predicate is evaluated for a player who has never completed that adventure
- **THEN** it evaluates to false

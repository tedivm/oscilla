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

The `item` leaf predicate SHALL accept an item reference name and evaluate to true when the player currently has at least one of that item in their inventory. Inventory is checked in both `stacks` (stackable items) and `instances` (non-stackable item instances). A non-stackable item held as an instance but not equipped still satisfies this predicate.

#### Scenario: Item is in inventory (stacks)

- **WHEN** an `item: old-key` predicate is evaluated for a player who has the `old-key` item in `stacks`
- **THEN** it evaluates to true

#### Scenario: Item is in inventory (non-stackable instance)

- **WHEN** an `item: iron-sword` predicate is evaluated for a player who has an `ItemInstance` with `item_ref="iron-sword"` in `instances`
- **THEN** it evaluates to true

#### Scenario: Item is not in inventory

- **WHEN** an `item: old-key` predicate is evaluated for a player whose inventory contains neither a stack nor an instance of `old-key`
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

---

### Requirement: skill condition leaf predicate

The `skill` leaf predicate SHALL have `name` (string, required) and `mode` (`"available"` | `"learned"`, default `"available"`).

`mode: "available"` evaluates to true when the named skill appears in `player.available_skills(registry)` (union of known, equipped, and held item skills). It requires the registry to be provided; without a registry it falls back to checking `player.known_skills` only.

`mode: "learned"` evaluates to true when the named skill is in `player.known_skills` only, regardless of inventory or equipment.

#### Scenario: skill condition available — skill in known_skills

- **WHEN** a `skill` predicate with `name: fireball, mode: available` is evaluated for a player with `"fireball"` in `known_skills`
- **THEN** it evaluates to true

#### Scenario: skill condition available — skill via equipped item

- **WHEN** a `skill` predicate with `name: arcane-blast, mode: available` is evaluated for a player whose equipped staff grants that skill
- **THEN** it evaluates to true

#### Scenario: skill condition learned — equipped skill not counted

- **WHEN** a `skill` predicate with `name: arcane-blast, mode: learned` is evaluated for a player who only has it via an equipped item
- **THEN** it evaluates to false

#### Scenario: skill condition false for unknown skill

- **WHEN** a `skill` predicate with `name: fireball, mode: available` is evaluated for a player with no fire skills in any source
- **THEN** it evaluates to false

---

### Requirement: Item equipped predicate (`item_equipped`)

The `item_equipped` leaf predicate SHALL accept an item reference name and evaluate to true when the player currently has an instance of that item occupying any equipment slot. A non-stackable item held in `instances` but not equipped SHALL evaluate to false. This predicate does not require a registry when used in conditions evaluated at the equipment-checking level; it evaluates directly from `player.equipment` and `player.instances`.

#### Scenario: Item is in an equipment slot

- **WHEN** an `item_equipped: rangers-cloak` predicate is evaluated for a player who has a `rangers-cloak` instance equipped
- **THEN** it evaluates to true

#### Scenario: Item is held but not equipped

- **WHEN** an `item_equipped: rangers-cloak` predicate is evaluated for a player who has the item in `instances` but not in any equipment slot
- **THEN** it evaluates to false

#### Scenario: Item is not in inventory at all

- **WHEN** an `item_equipped: rangers-cloak` predicate is evaluated for a player who does not have the item
- **THEN** it evaluates to false

---

### Requirement: Item held label predicate (`item_held_label`)

The `item_held_label` leaf predicate SHALL accept a label string and evaluate to true when any item in the player's `stacks` or `instances` carries that label in its `ItemSpec.labels` list. This predicate requires a registry to resolve item specs. Without a registry it SHALL log a warning and return false.

#### Scenario: Stackable item with label is held

- **WHEN** an `item_held_label: cursed` predicate is evaluated for a player who has a stackable item with `labels: [cursed]` in their stacks
- **THEN** it evaluates to true

#### Scenario: Non-stackable instance with label is held

- **WHEN** an `item_held_label: cursed` predicate is evaluated for a player who has a non-stackable instance with `labels: [cursed]` in their instances
- **THEN** it evaluates to true (regardless of whether the item is equipped)

#### Scenario: No held item has the label

- **WHEN** an `item_held_label: cursed` predicate is evaluated for a player whose inventory contains no item with `labels: [cursed]`
- **THEN** it evaluates to false

#### Scenario: No registry — returns false with warning

- **WHEN** an `item_held_label` predicate is evaluated without a registry
- **THEN** it evaluates to false and a WARNING is logged

---

### Requirement: Any item equipped label predicate (`any_item_equipped`)

The `any_item_equipped` leaf predicate SHALL accept a label string and evaluate to true when any currently equipped item carries that label in its `ItemSpec.labels` list. Items held but not equipped SHALL NOT satisfy the predicate. This predicate requires a registry to resolve item specs. Without a registry it SHALL log a warning and return false.

#### Scenario: Equipped item has the label

- **WHEN** an `any_item_equipped: ranger-set` predicate is evaluated for a player who has a `ranger-set`-labeled item in an equipment slot
- **THEN** it evaluates to true

#### Scenario: Labeled item is held but not equipped

- **WHEN** an `any_item_equipped: ranger-set` predicate is evaluated for a player whose `ranger-set`-labeled item is in `instances` but not in `equipment`
- **THEN** it evaluates to false

#### Scenario: No equipped item has the label

- **WHEN** an `any_item_equipped: ranger-set` predicate is evaluated for a player with no equipped items carrying that label
- **THEN** it evaluates to false

#### Scenario: No registry — returns false with warning

- **WHEN** an `any_item_equipped` predicate is evaluated without a registry
- **THEN** it evaluates to false and a WARNING is logged

---

### Requirement: New predicates compose with `not`, `all`, `any`

The three new predicates (`item_equipped`, `item_held_label`, `any_item_equipped`) SHALL participate in `not`, `all`, and `any` condition nodes identically to all other leaf predicates. Negation, conjunction, and disjunction of these predicates are fully supported.

#### Scenario: Negation of item_held_label

- **WHEN** a `not: {item_held_label: cursed}` condition is evaluated for a player with no cursed items
- **THEN** it evaluates to true

---

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

---

### Requirement: quest_stage condition type is supported

The condition evaluator SHALL support `type: quest_stage` conditions. The evaluator SHALL read `player.active_quests` dict and return `true` if and only if the quest is present and the current stage value equals the declared `stage` field. No registry access is required to evaluate this condition.

#### Scenario: Conjunction requiring both cloak equipped and ranger-set weapon equipped

- **WHEN** an `all: [{item_equipped: rangers-cloak}, {any_item_equipped: ranger-set}]` condition is evaluated for a player with both conditions met
- **THEN** it evaluates to true

---

### Requirement: `CharacterStatCondition` supports a `stat_source` field

`CharacterStatCondition` SHALL accept an optional `stat_source: "base" | "effective"` field (default `"effective"`). The field controls which stat values are compared.

- When `stat_source` is `"effective"` (or omitted), the evaluator SHALL use `player.effective_stats(registry, exclude_item=exclude_item)` when a registry is available. If no registry is available, it falls back to `player.stats`.
- When `stat_source` is `"base"`, the evaluator SHALL always use `player.stats` regardless of whether a registry is present.

The `evaluate()` function SHALL accept an `exclude_item: str | None = None` parameter. When set, this value is forwarded to `effective_stats()` so the named item's stat modifier contributions are excluded from the result. The parameter is forwarded unchanged through `AllCondition`, `AnyCondition`, and `NotCondition` recursive calls.

#### Scenario: stat_source effective uses gear bonuses

- **WHEN** a `character_stat: {name: strength, gte: 15}` condition (default `stat_source: effective`) is evaluated for a player with base strength 12 and an equipped ring providing `+5 strength`
- **THEN** it evaluates to true (effective strength is 17)

#### Scenario: stat_source base ignores gear bonuses

- **WHEN** a `character_stat: {name: strength, gte: 15, stat_source: base}` condition is evaluated for the same player (base 12, ring +5)
- **THEN** it evaluates to false (base strength is 12)

#### Scenario: exclude_item strips the excluded item's bonuses from effective stats

- **WHEN** `evaluate()` is called with `exclude_item="vorpal-blade"` and the condition is `character_stat: {name: strength, gte: 15}` with the player having base strength 12 and Vorpal Blade equipped with `+5 strength`
- **THEN** it evaluates to false (effective strength excluding Vorpal Blade's own bonus is 12)

#### Scenario: stat_source base is unaffected by exclude_item

- **WHEN** `evaluate()` is called with `exclude_item="vorpal-blade"` and the condition uses `stat_source: base`
- **THEN** the result is the same as without `exclude_item` — base stats are never modified by the exclusion

---

### Requirement: Calendar condition predicates compose with existing tree nodes

All eight new calendar predicates (`season_is`, `moon_phase_is`, `zodiac_is`, `chinese_zodiac_is`, `month_is`, `day_of_week_is`, `date_is`, `time_between`) SHALL be valid leaf node types within the existing `Condition` union and SHALL compose with `all`, `any`, and `not` branch nodes identically to all other leaf predicates.

#### Scenario: calendar predicate under all node

- **WHEN** an `all` condition contains a `season_is` predicate and a `milestone` predicate, both of which are satisfied
- **THEN** the `all` node evaluates to true

#### Scenario: calendar predicate negated under not node

- **WHEN** a `not` condition wraps a `month_is: 10` predicate and the current month is July
- **THEN** the `not` node evaluates to true

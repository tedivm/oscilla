## MODIFIED Requirements

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

## ADDED Requirements

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

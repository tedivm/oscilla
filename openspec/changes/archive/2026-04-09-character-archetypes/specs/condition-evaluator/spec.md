## REMOVED Requirements

### Requirement: Class leaf predicate (placeholder)

**Reason:** The `class` condition predicate was a no-op placeholder that always evaluated to `true`. It is replaced by the fully implemented `has_archetype`, `has_all_archetypes`, `has_any_archetypes`, and `archetype_count` predicates from the archetype-conditions capability.

**Migration:** Replace `type: class` conditions with the appropriate archetype predicate:

- `type: class, name: warrior` → `type: has_archetype, name: warrior`
- Any condition relying on the always-true behavior should be removed entirely (it had no effect) or replaced with a meaningful archetype check.

The `ClassCondition` model, the `case ClassCondition()` branch in `conditions.py`, and `ClassCondition` from the `Condition` union are all removed.

---

## ADDED Requirements

### Requirement: has_archetype leaf predicate

The `has_archetype` leaf predicate SHALL evaluate to true when the player's `archetypes` set contains the specified name. See the `archetype-conditions` capability spec for full details and scenarios.

#### Scenario: has_archetype true when archetype is held

- **WHEN** a `has_archetype: {name: warrior}` predicate is evaluated for a player with `"warrior"` in `archetypes`
- **THEN** it evaluates to true

---

### Requirement: has_all_archetypes leaf predicate

The `has_all_archetypes` leaf predicate SHALL evaluate to true when the player holds all named archetypes. See the `archetype-conditions` capability spec for full details.

#### Scenario: has_all_archetypes true when all are held

- **WHEN** a `has_all_archetypes: {names: [warrior, mage]}` predicate is evaluated for a player holding both
- **THEN** it evaluates to true

---

### Requirement: has_any_archetypes leaf predicate

The `has_any_archetypes` leaf predicate SHALL evaluate to true when the player holds at least one of the named archetypes. See the `archetype-conditions` capability spec for full details.

#### Scenario: has_any_archetypes true when at least one is held

- **WHEN** a `has_any_archetypes: {names: [warrior, paladin]}` predicate is evaluated for a player holding `"paladin"`
- **THEN** it evaluates to true

---

### Requirement: archetype_count leaf predicate

The `archetype_count` leaf predicate SHALL evaluate to true when the count of held archetypes satisfies a numeric comparison. See the `archetype-conditions` capability spec for full details.

#### Scenario: archetype_count gte true when sufficient archetypes held

- **WHEN** an `archetype_count: {gte: 2}` predicate is evaluated for a player holding three archetypes
- **THEN** it evaluates to true

---

### Requirement: archetype_ticks_elapsed leaf predicate

The `archetype_ticks_elapsed` leaf predicate SHALL evaluate to true when the `internal_ticks` elapsed since the named archetype was granted satisfies the comparator. If the archetype is not held, it evaluates to false. At least one of `gte` or `lte` must be specified. See the `archetype-conditions` capability spec for full details.

#### Scenario: archetype_ticks_elapsed true when enough ticks elapsed

- **WHEN** `archetype_ticks_elapsed: {name: warrior, gte: 5}` is evaluated and 6 ticks have elapsed since `"warrior"` was granted
- **THEN** it evaluates to true

#### Scenario: archetype_ticks_elapsed false when archetype not held

- **WHEN** `archetype_ticks_elapsed: {name: warrior, gte: 0}` is evaluated and the player does not hold `"warrior"`
- **THEN** it evaluates to false

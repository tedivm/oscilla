## ADDED Requirements

### Requirement: Enemy stat leaf predicate

The `enemy_stat` leaf predicate SHALL accept a `stat: str` key and standard comparator fields (`gte`, `lte`, `gt`, `lt`, `eq`). It SHALL evaluate to true when the named key in the current combat context's `enemy_stats` satisfies the comparator. It SHALL evaluate to `false` with a logged warning when called outside a combat context (i.e., when `enemy_stats` is `None`).

#### Scenario: Enemy stat condition evaluates true

- **WHEN** an `enemy_stat` condition with `stat: hp, lte: 0` is evaluated and `enemy_stats["hp"]` is 0
- **THEN** it evaluates to true

#### Scenario: Enemy stat condition evaluates false

- **WHEN** an `enemy_stat` condition with `stat: hp, lte: 0` is evaluated and `enemy_stats["hp"]` is 25
- **THEN** it evaluates to false

#### Scenario: Enemy stat condition outside combat context

- **WHEN** `evaluate(EnemyStatCondition(stat="hp", lte=0), player, enemy_stats=None)` is called
- **THEN** it returns `false` and logs a warning

---

### Requirement: Combat stat leaf predicate

The `combat_stat` leaf predicate SHALL accept a `stat: str` key and standard comparator fields. It SHALL evaluate to true when the named key in the current combat context's `combat_stats` satisfies the comparator. It SHALL evaluate to `false` with a logged warning when called outside a combat context (i.e., when `combat_stats` is `None`). It is valid in `CombatSystem` defeat conditions and `SystemSkillEntry` conditions evaluated during combat rounds.

#### Scenario: Combat stat condition evaluates true

- **WHEN** a `combat_stat` condition with `stat: lives, lte: 0` is evaluated and `combat_stats["lives"]` is 0
- **THEN** it evaluates to true

#### Scenario: Combat stat condition outside combat context

- **WHEN** `evaluate(CombatStatCondition(stat="lives", lte=0), player, combat_stats=None)` is called
- **THEN** it returns `false` and logs a warning

## MODIFIED Requirements

### Requirement: Logical condition tree structure

The `evaluate()` function signature SHALL accept optional `enemy_stats: Dict[str, int] | None = None` and `combat_stats: Dict[str, int] | None = None` parameters. These are forwarded recursively to all child node evaluations so that `enemy_stat` and `combat_stat` leaf predicates resolve correctly at any depth in the condition tree. The new parameters are optional to preserve compatibility with all existing non-combat call sites.

#### Scenario: Enemy stat condition nested inside all/any

- **WHEN** an `all` condition contains an `enemy_stat` leaf and both the logical operator and the leaf are evaluated with `enemy_stats` in context
- **THEN** the `enemy_stats` dict is available to the leaf and it evaluates correctly

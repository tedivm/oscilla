## MODIFIED Requirements

### Requirement: Prestige count leaf predicate

The `prestige_count` leaf predicate SHALL accept a numeric comparison (`gte`, `lte`, `eq`, `gt`, `lt`, `mod`) and evaluate to true when the player's prestige count satisfies the comparison. In YAML the condition is expressed as `type: prestige_count` (the discriminator key is `prestige_count`, not `iteration`). At least one comparator field MUST be supplied; omitting all comparators is a validation error.

#### Scenario: Player has enough prestiges

- **WHEN** a `{type: prestige_count, gte: 1}` predicate is evaluated for a player with prestige_count 2
- **THEN** it evaluates to true

#### Scenario: Player has not prestiged

- **WHEN** a `{type: prestige_count, gte: 1}` predicate is evaluated for a player with prestige_count 0
- **THEN** it evaluates to false

#### Scenario: Retired iteration type key rejected

- **WHEN** a condition block with `type: iteration` is deserialized
- **THEN** Pydantic raises a ValidationError (the old key is no longer recognized)

#### Scenario: Missing comparator is rejected

- **WHEN** a `{type: prestige_count}` object with no comparison fields is deserialized
- **THEN** a validation error is raised indicating at least one comparator must be provided

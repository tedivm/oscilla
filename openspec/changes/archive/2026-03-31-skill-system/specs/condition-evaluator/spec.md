## ADDED Requirements

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

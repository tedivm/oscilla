## MODIFIED Requirements

### Requirement: CharacterConfig manifest defines player stats

The `CharacterConfig` manifest SHALL define `public_stats` and `hidden_stats` as lists of `StatDefinition`. Each `StatDefinition` SHALL have a `name` (string), `type` (`"int"` or `"bool"` — `"float"` is not a valid type), `default` (`int | bool | None`), and `description` (string, optional). Each `StatDefinition` for an `int` stat MAY include an optional `bounds: StatBounds` object with `min: int | None` and `max: int | None` fields. Setting `bounds` on a `bool` stat is a content load error. Stat names SHALL be unique across `public_stats` and `hidden_stats` within the same `CharacterConfig`; duplicate names SHALL be a content load error.

#### Scenario: Valid character config with int and bool stats loads successfully

- **WHEN** a `CharacterConfig` manifest declares `int` and `bool` stats with valid names and defaults
- **THEN** the manifest loads without error and the stat definitions are accessible via `CharacterConfigSpec`

#### Scenario: Float stat type is rejected

- **WHEN** a `CharacterConfig` manifest declares a stat with `type: float`
- **THEN** the content loader raises a `ValidationError` identifying the invalid stat type

#### Scenario: CharacterConfig with bounds on int stat loads successfully

- **WHEN** a `CharacterConfig` declares an `int` stat with `bounds: { min: 0, max: 1000000 }`
- **THEN** the manifest loads without error and the stat's bounds are accessible

#### Scenario: CharacterConfig with bounds on bool stat is a load error

- **WHEN** a `CharacterConfig` declares a `bool` stat with any `bounds` value
- **THEN** the content loader raises a `ValidationError` identifying the stat name and invalid field

#### Scenario: Duplicate stat names are a load error

- **WHEN** a `CharacterConfig` manifest declares two stats with the same name (even if one is public and one hidden)
- **THEN** the content loader raises a `ValidationError` listing the duplicate names

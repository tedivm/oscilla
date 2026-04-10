## MODIFIED Requirements

### Requirement: Supported entity kinds

The manifest system SHALL support the following `kind` values: `Region`, `Location`, `Adventure`, `Enemy`, `Item`, `Recipe`, `Quest`, `Archetype`, `Game`, `CharacterConfig`, `Skill`, `Buff`, and `LootTable`.

The `Class` kind is removed. (**BREAKING**: content using `kind: Class` must migrate to `kind: Archetype`.)

#### Scenario: Each kind maps to a Pydantic model

- **WHEN** a manifest with a supported `kind` is loaded
- **THEN** it is validated against the corresponding Pydantic schema and stored in the content registry under that kind's namespace

#### Scenario: Archetype kind is loaded into registry.archetypes

- **WHEN** a manifest with `kind: Archetype` is loaded
- **THEN** it is registered in `ContentRegistry.archetypes` under its `metadata.name`

#### Scenario: Class kind is rejected as unknown

- **WHEN** a manifest with `kind: Class` is loaded
- **THEN** the loader raises a `LoadError` with an "Unknown kind" message

## MODIFIED Requirements

### Requirement: CharacterState does not carry character_class

`CharacterState` SHALL NOT contain a `character_class` field. The field was always `None` and has no engine semantics; archetypes serve the role it was intended for.

`CharacterState.to_dict()` SHALL NOT include a `character_class` key in its output.

`CharacterState.from_dict()` SHALL silently ignore a `"character_class"` key if present in the input data, to support backward-compatible deserialization of legacy serialized blobs.

The `character_iterations` table SHALL NOT have a `character_class` column. An Alembic migration SHALL drop the column.

#### Scenario: to_dict does not include character_class

- **GIVEN** a `CharacterState` instance
- **WHEN** `to_dict()` is called
- **THEN** the returned dict does not contain the key `"character_class"`

#### Scenario: from_dict accepts legacy blobs with character_class without error

- **GIVEN** a saved dict that contains `"character_class": null` (legacy format)
- **WHEN** `CharacterState.from_dict()` is called with this dict
- **THEN** no exception is raised and the resulting `CharacterState` is valid

## NEW Requirements

### Requirement: `evaluate()` resolves `CustomConditionRef` via the registry

The `evaluate()` function in `oscilla/engine/conditions.py` SHALL add a `CustomConditionRef` case arm to its match block, inserted before the wildcard `case _:` arm.

The arm SHALL:

1. Look up `registry.custom_conditions.get(n)` where `n` is `condition.name`.
2. If `registry` is `None`: log a warning at `WARNING` level and return `False`.
3. If the name is not found in the registry: log a warning at `WARNING` level and return `False`.
4. If found: return `evaluate(defn.spec.condition, player, registry, exclude_item)` — delegating fully to the stored body.

The `CustomConditionRef` import SHALL be added to the existing import block from `oscilla.engine.models.base`.

#### Scenario: type: custom resolves to its body and evaluates correctly

- **GIVEN** a `ContentRegistry` with a `CustomConditionManifest` named `"gate-level-5"` whose body is `LevelCondition(value=5)`
- **AND** a player at level 3
- **WHEN** `evaluate(CustomConditionRef(type="custom", name="gate-level-5"), player, registry)` is called
- **THEN** the result is `False`

- **GIVEN** the same registry and a player at level 7
- **WHEN** `evaluate(CustomConditionRef(type="custom", name="gate-level-5"), player, registry)` is called
- **THEN** the result is `True`

#### Scenario: type: custom with registry=None returns False and logs a warning

- **GIVEN** `registry=None`
- **WHEN** `evaluate(CustomConditionRef(type="custom", name="anything"), player, registry=None)` is called
- **THEN** the result is `False`
- **AND** a `WARNING`-level log message mentioning the condition name is emitted

#### Scenario: type: custom referencing an unknown name returns False and logs a warning

- **GIVEN** a `ContentRegistry` with no custom conditions registered
- **WHEN** `evaluate(CustomConditionRef(type="custom", name="no-such-condition"), player, registry)` is called
- **THEN** the result is `False`
- **AND** a `WARNING`-level log message mentioning `"no-such-condition"` is emitted

#### Scenario: type: custom composes — body references another custom condition

- **GIVEN** a registry with:
  - `"inner"` → `LevelCondition(value=5)`
  - `"outer"` → `CustomConditionRef(name="inner")`
- **AND** a player at level 7
- **WHEN** `evaluate(CustomConditionRef(type="custom", name="outer"), player, registry)` is called
- **THEN** the result is `True` (resolution is transitive)

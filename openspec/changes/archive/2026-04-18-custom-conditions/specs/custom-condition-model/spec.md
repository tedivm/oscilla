## NEW Requirements

### Requirement: `CustomConditionSpec` and `CustomConditionManifest` Pydantic models exist

A new file `oscilla/engine/models/custom_condition.py` SHALL define two Pydantic models:

- `CustomConditionSpec` — holds `display_name: str | None = None` and `condition: Condition`.
- `CustomConditionManifest` — extends `ManifestEnvelope` with `kind: Literal["CustomCondition"]` and `spec: CustomConditionSpec`.

The `condition` field on `CustomConditionSpec` SHALL accept the full `Condition` union, including `CustomConditionRef`, enabling composition.

#### Scenario: minimal manifest parses without display_name

- **GIVEN** the YAML:

  ```yaml
  apiVersion: oscilla/v1
  kind: CustomCondition
  metadata:
    name: gate-level-5
  spec:
    condition:
      type: level
      value: 5
  ```

- **WHEN** parsed through `CustomConditionManifest`
- **THEN** `manifest.spec.display_name` is `None` and `manifest.spec.condition` is a `LevelCondition` with `value=5`

#### Scenario: manifest with display_name parses correctly

- **GIVEN** the YAML:

  ```yaml
  apiVersion: oscilla/v1
  kind: CustomCondition
  metadata:
    name: gate-level-5
  spec:
    displayName: "Level 5+"
    condition:
      type: level
      value: 5
  ```

- **WHEN** parsed through `CustomConditionManifest`
- **THEN** `manifest.spec.display_name` is `"Level 5+"`

---

### Requirement: `CustomConditionRef` is a member of the `Condition` union in `base.py`

A new leaf model `CustomConditionRef` SHALL be added to `oscilla/engine/models/base.py` and appended to the `Condition` union discriminated by `type: Literal["custom"]`.

`CustomConditionRef` SHALL have:

- `type: Literal["custom"]`
- `name: str` — the `metadata.name` of the target `CustomCondition` manifest

The discriminator value `"custom"` SHALL not conflict with any existing condition type literal.

#### Scenario: CustomConditionRef parses from YAML type field

- **GIVEN** the YAML fragment `{ type: custom, name: my-condition }`
- **WHEN** parsed as a `Condition`
- **THEN** the result is a `CustomConditionRef` with `name="my-condition"`

---

### Requirement: `CustomConditionManifest` is registered in `MANIFEST_REGISTRY` and `__all__`

`oscilla/engine/models/__init__.py` SHALL:

- Import `CustomConditionManifest` from `oscilla.engine.models.custom_condition`.
- Add `"CustomCondition": CustomConditionManifest` to `MANIFEST_REGISTRY`.
- Add `"CustomConditionManifest"` to `__all__`.

#### Scenario: MANIFEST_REGISTRY resolves CustomCondition kind

- **GIVEN** `MANIFEST_REGISTRY`
- **WHEN** accessed with key `"CustomCondition"`
- **THEN** returns `CustomConditionManifest`

---

### Requirement: `ContentRegistry` has a `custom_conditions` field and `build()` handles the kind

`oscilla/engine/registry.py` SHALL add:

- `self.custom_conditions: KindRegistry[CustomConditionManifest] = KindRegistry()` to `ContentRegistry.__init__()`.
- A `case "CustomCondition":` arm in `build()` that calls `registry.custom_conditions.register(cast(CustomConditionManifest, m))`.
- The import of `CustomConditionManifest` alongside other manifest imports.

#### Scenario: build() populates custom_conditions from a manifest list

- **GIVEN** a list of manifests that includes a `CustomConditionManifest` with `metadata.name = "my-gate"`
- **WHEN** `ContentRegistry.build(manifests)` is called
- **THEN** `registry.custom_conditions.get("my-gate")` returns that manifest

#### Scenario: build() does not error when no CustomCondition manifests are present

- **GIVEN** a list of manifests with no `CustomCondition` kind entries
- **WHEN** `ContentRegistry.build(manifests)` is called
- **THEN** no error is raised and `registry.custom_conditions` is empty

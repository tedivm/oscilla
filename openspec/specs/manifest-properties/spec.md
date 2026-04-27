# Manifest Properties

## Purpose

Provides a `properties` dict on every manifest spec, exposing author-defined scalar values as `this` in formula and template contexts. Enables parameterized formulas (e.g., damage formulas that read `this.get('damage_die', 4)`) without hardcoding values.

## Requirements

### Requirement: All spec models inherit from BaseSpec with a properties field

A new `BaseSpec(BaseModel)` parent class SHALL be introduced. All spec models (`EnemySpec`, `ItemSpec`, `AdventureSpec`, etc.) SHALL inherit from `BaseSpec` instead of `BaseModel`. `BaseSpec` SHALL carry `properties: Dict[str, int | float | str | bool]` with a `default_factory=dict`.

#### Scenario: Spec model has empty properties by default

- **WHEN** a manifest is loaded without a `properties` field in its `spec`
- **THEN** the parsed spec has `properties == {}`

#### Scenario: Spec model accepts scalar property values

- **WHEN** a manifest's `spec` declares `properties: {damage_die: 6, label: "sharp"}`
- **THEN** the parsed spec has `properties == {"damage_die": 6, "label": "sharp"}`

#### Scenario: Non-scalar property values are rejected

- **WHEN** a manifest's `spec` declares `properties: {items: [a, b]}`
- **THEN** Pydantic validation raises an error for the non-scalar value

---

### Requirement: this is available in CombatFormulaContext

`CombatFormulaContext` SHALL have a `this: Dict[str, int | float | str | bool]` field populated from the triggering manifest's `properties` dict (item, skill, or enemy, depending on what triggers the formula).

#### Scenario: Formula reads this.get() value

- **WHEN** a damage formula `{{ this.get('damage_die', 4) * player['strength'] }}` is rendered with `this = {"damage_die": 6}` and `player["strength"] = 5`
- **THEN** the result is `30`

#### Scenario: Formula uses this.get() default when key missing

- **WHEN** a damage formula `{{ this.get('damage_die', 4) }}` is rendered with `this = {}`
- **THEN** the result is `4`

---

### Requirement: this is available in ExpressionContext

`ExpressionContext` SHALL have a `this: Dict[str, int | float | str | bool]` field populated from the current manifest's `properties` dict (e.g., the adventure manifest's properties for adventure step templates).

#### Scenario: Adventure template reads this value

- **WHEN** an adventure step template `{{ this.get('gold_reward', 10) }}` is rendered and the adventure has `properties: {gold_reward: 50}`
- **THEN** the rendered output is `"50"`

#### Scenario: Template uses this.get() default when properties empty

- **WHEN** an adventure step template `{{ this.get('gold_reward', 10) }}` is rendered and the adventure has no `properties`
- **THEN** the rendered output is `"10"`

---

### Requirement: Mock context for load-time validation includes this

The `build_mock_context()` function SHALL accept an optional `manifest_properties` parameter. When provided, the mock context SHALL include `this` populated from those properties. Load-time template validation SHALL pass the manifest's `properties` dict as `manifest_properties`.

#### Scenario: Load-time validation uses manifest properties for this

- **WHEN** a manifest with `properties: {damage_die: 6}` has a formula `{{ this.get('damage_die', 4) }}`
- **THEN** load-time mock rendering succeeds and produces `6`

#### Scenario: Load-time validation with empty this uses defaults

- **WHEN** a manifest with no `properties` has a formula `{{ this.get('damage_die', 4) }}`
- **THEN** load-time mock rendering succeeds and produces `4`

---

### Requirement: Inherited properties are merged during inheritance resolution

When a child manifest inherits from a base, the child's `properties` dict is merged onto the base's `properties` dict using the same merge semantics as other spec fields. The `properties+:` syntax SHALL extend the base's properties dict.

#### Scenario: Child properties override base properties

- **WHEN** a base has `properties: {damage_die: 4}` and a child has `properties: {damage_die: 6}`
- **THEN** the merged result has `properties: {damage_die: 6}`

#### Scenario: Child properties extend base properties with +

- **WHEN** a base has `properties: {damage_die: 4}` and a child has `properties+: {label: "sharp"}`
- **THEN** the merged result has `properties: {damage_die: 4, label: "sharp"}`

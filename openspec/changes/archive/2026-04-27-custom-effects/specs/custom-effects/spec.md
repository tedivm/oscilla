# Custom Effects

## Purpose

Defines the `CustomEffect` manifest kind, the `type: custom_effect` effect leaf, parameter schema with type checking, runtime resolution with `params` injection, composition support, and load-time validation — as a macro layer for reusable, parameterized effect sequences.

---

## ADDED Requirements

### Requirement: `CustomEffect` manifest kind with parameter schema

The engine SHALL support a `kind: CustomEffect` manifest with a `CustomEffectSpec` containing: a `displayName` (optional), a `description` (optional), a `parameters` list of `CustomEffectParameter` entries (each with `name`, `type`, and optional `default`), and an `effects` list of standard `Effect` entries (minimum length 1). Parameter names within a single `CustomEffectSpec` SHALL be unique. The `type` field SHALL be one of `int`, `float`, `str`, `bool`.

#### Scenario: valid CustomEffect with typed parameters

- **GIVEN** a `CustomEffect` manifest with `parameters: [{name: percent, type: float, default: 50}]` and `effects: [{type: heal, amount: full}]`
- **WHEN** content is loaded
- **THEN** the manifest is registered in `registry.custom_effects` under its `metadata.name`

#### Scenario: duplicate parameter names raise validation error

- **GIVEN** a `CustomEffect` manifest with two parameters named `"value"`
- **WHEN** content is loaded
- **THEN** the loader raises a Pydantic validation error for duplicate parameter names

#### Scenario: empty effects list raises validation error

- **GIVEN** a `CustomEffect` manifest with `effects: []`
- **WHEN** content is loaded
- **THEN** the loader raises a Pydantic validation error for `min_length=1` on `effects`

### Requirement: `type: custom_effect` effect leaf with params

The `Effect` discriminated union SHALL include a `CustomEffectRef` arm with `type: Literal["custom_effect"]`, a `name` field referencing a `CustomEffect` manifest, and an optional `params` dict (`Dict[str, int | float | str | bool]`). At runtime, the engine SHALL look up the named `CustomEffect` in `registry.custom_effects`, merge the manifest's parameter defaults with the call-site `params`, inject the merged dict as `params` on the `ExpressionContext`, and execute each body effect sequentially.

#### Scenario: basic custom effect invocation

- **GIVEN** a `CustomEffect` `"heal_pct"` with parameter `percent` (default 50) and body `[{type: stat_change, stat: hp, amount: "{{ params.percent }}"}]`
- **WHEN** an `Item` with `use_effects: [{type: custom_effect, name: heal_pct, params: {percent: 30}}]` is used by a player with `hp: 80`
- **THEN** the player's `hp` is increased by 30 (to 110, capped at max_hp)

#### Scenario: custom effect with no params uses all defaults

- **GIVEN** a `CustomEffect` `"heal_pct"` with parameter `percent` (default 50)
- **WHEN** an `Item` with `use_effects: [{type: custom_effect, name: heal_pct}]` is used
- **THEN** the body executes with `params.percent` = 50

#### Scenario: custom effect body effects execute sequentially with shared state

- **GIVEN** a `CustomEffect` with two body effects: `stat_change` on `hp` (+10) then `milestone_grant`
- **WHEN** the custom effect is invoked
- **THEN** both effects fire in order, and the milestone grant sees the updated `hp`

### Requirement: `params` variable available in body effect templates

The `ExpressionContext` dataclass SHALL have a `params` field (`Dict[str, int | float | str | bool]`, default empty dict). The `GameTemplateEngine.render()` method SHALL expose `params` in the Jinja2 render context. Template expressions in body effect fields (e.g., `amount: "{{ params.percent / 100 * player.stats['max_hp'] }}"`) SHALL resolve `params` from the merged parameter dict.

#### Scenario: template expression references params

- **GIVEN** a `CustomEffect` with parameter `multiplier` (default 2) and body `[{type: stat_change, stat: strength, amount: "{{ params.multiplier * 5 }}"}]`
- **WHEN** invoked with `params: {multiplier: 3}` on a player with `strength: 10`
- **THEN** the player's `strength` is increased by 15 (to 25)

#### Scenario: params.get with default works when param not set

- **GIVEN** a `CustomEffect` with parameter `bonus` (default 10) and body using `{{ params.get('bonus', 0) }}`
- **WHEN** invoked with no `params` at call site
- **THEN** the template resolves to 10 (the default)

### Requirement: Custom effects can compose custom effects

A `CustomEffect` body MAY contain `type: custom_effect` effects that reference other `CustomEffect` manifests. Each nested invocation SHALL get its own `params` frame derived from its call-site `params` dict merged with its manifest's defaults. The outer `params` frame SHALL NOT leak into the inner context — each level is isolated.

#### Scenario: nested custom effect A → B

- **GIVEN** `CustomEffect` "a" with body `[{type: custom_effect, name: "b", params: {value: 50}}]`, and `CustomEffect` "b" with parameter `value` and body `[{type: stat_set, stat: hp, value: "{{ params.value }}"}]`
- **WHEN** "a" is invoked
- **THEN** the player's `hp` is set to 50

#### Scenario: nested params isolation

- **GIVEN** `CustomEffect` "outer" with parameter `x` (default 1) and body that calls "inner" with `params: {x: 10}`, then uses `{{ params.x }}` in its own subsequent effect
- **WHEN** "outer" is invoked with no params
- **THEN** the inner effect sees `x=10`, and the outer's subsequent effect sees `x=1` (its own default)

### Requirement: Dangling `type: custom_effect` references raise `ContentLoadError`

At content load time, every `CustomEffectRef` that appears anywhere in the content package SHALL be checked against `registry.custom_effects`. If the referenced `name` is not registered, the loader SHALL raise a `ContentLoadError` identifying the dangling reference and the manifest in which it was found.

#### Scenario: item use_effects references unknown CustomEffect

- **GIVEN** an `Item` manifest with `use_effects: [{type: custom_effect, name: nonexistent}]`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` naming `"nonexistent"` and the item manifest

#### Scenario: CustomEffect body references unknown CustomEffect

- **GIVEN** a `CustomEffect` with body `[{type: custom_effect, name: ghost}]`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError`

#### Scenario: all references present — no error

- **GIVEN** every `CustomEffectRef` in the package resolves to a registered `CustomEffect` manifest
- **WHEN** content is loaded
- **THEN** no `ContentLoadError` is raised for dangling references

### Requirement: Circular `CustomEffect` dependency chains raise `ContentLoadError`

At content load time, the dependency graph among `CustomEffect` manifests SHALL be inspected for cycles using depth-first search back-edge detection. If any cycle is found, the loader SHALL raise a `ContentLoadError` naming the cycle participants.

#### Scenario: direct self-reference raises ContentLoadError

- **GIVEN** a `CustomEffect` manifest with `metadata.name: self-ref` whose body contains `{type: custom_effect, name: self-ref}`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` identifying the cycle

#### Scenario: two-node cycle raises ContentLoadError

- **GIVEN** `CustomEffect` `"a"` references `"b"` and `"b"` references `"a"`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` identifying the `a → b → a` cycle

#### Scenario: valid diamond dependency does not raise

- **GIVEN** `CustomEffect` `"a"` references both `"b"` and `"c"`, and both `"b"` and `"c"` reference `"d"`, with no back-edges
- **WHEN** content is loaded
- **THEN** no cycle error is raised

### Requirement: Unknown parameters at call site raise `ContentLoadError`

At content load time, each key in a `CustomEffectRef.params` dict SHALL be checked against the target `CustomEffect`'s declared parameter schema. If a key is not declared, the loader SHALL raise a `ContentLoadError` naming the unknown parameter and the list of valid parameter names.

#### Scenario: call site passes undeclared parameter

- **GIVEN** a `CustomEffect` with parameters `[name: percent]` and a call site with `params: {percent: 25, nonexistent: true}`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` naming `"nonexistent"` as an unknown parameter

#### Scenario: call site only passes declared parameters

- **GIVEN** a `CustomEffect` with parameters `[name: percent, name: stat]` and a call site with `params: {percent: 25}`
- **WHEN** content is loaded
- **THEN** no error is raised

### Requirement: Parameter type mismatches raise `ContentLoadError`

At content load time, each value in a `CustomEffectRef.params` dict SHALL be checked against the target parameter's declared type. A `bool` value SHALL be rejected when the declared type is `int` (due to Python's `bool` being a subclass of `int`). An `int` value SHALL be accepted when the declared type is `float`.

#### Scenario: bool passed where int expected

- **GIVEN** a `CustomEffect` with parameter `amount` (type `int`) and a call site with `params: {amount: true}`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` for type mismatch

#### Scenario: int passed where float expected

- **GIVEN** a `CustomEffect` with parameter `percent` (type `float`) and a call site with `params: {percent: 25}`
- **WHEN** content is loaded
- **THEN** no error is raised — `int` is accepted as `float`

#### Scenario: str passed where int expected

- **GIVEN** a `CustomEffect` with parameter `amount` (type `int`) and a call site with `params: {amount: "hello"}`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` for type mismatch

### Requirement: Missing required parameters raise `ContentLoadError`

A parameter with `default: null` (or no `default` field) is required. At content load time, if a call site does not supply a required parameter, the loader SHALL raise a `ContentLoadError` naming the missing parameter(s).

#### Scenario: required parameter omitted

- **GIVEN** a `CustomEffect` with parameter `stat` (type `str`, no default) and a call site with `params: {}`
- **WHEN** content is loaded
- **THEN** the loader raises a `ContentLoadError` naming `"stat"` as a missing required parameter

#### Scenario: required parameter provided

- **GIVEN** a `CustomEffect` with parameter `stat` (type `str`, no default) and a call site with `params: {stat: "hp"}`
- **WHEN** content is loaded
- **THEN** no error is raised

### Requirement: `ContentRegistry` stores CustomEffect manifests

The `ContentRegistry` SHALL have a `custom_effects: KindRegistry[CustomEffectManifest]` field. `ContentRegistry.build()` SHALL register `CustomEffect` manifests in this registry.

#### Scenario: CustomEffect registered in registry

- **GIVEN** a content package with a `CustomEffect` manifest named `"heal_pct"`
- **WHEN** content is loaded and the registry is built
- **THEN** `registry.custom_effects.get("heal_pct")` returns the manifest

### Requirement: Custom effect with `end_adventure` in body propagates signal

When a `CustomEffect` body contains an `EndAdventureEffect`, the `_EndSignal` SHALL propagate up through the custom effect handler and be caught by the step runner, ending the adventure as if the effect were inline.

#### Scenario: custom effect body ends adventure

- **GIVEN** a `CustomEffect` with body `[{type: stat_change, ...}, {type: end_adventure, outcome: completed}]`
- **WHEN** the custom effect is invoked during an adventure step
- **THEN** the adventure ends with outcome `"completed"` after the `stat_change` fires

---

## MODIFIED Requirements

### Requirement: `ExpressionContext` exposes `params` in template render context

The `ExpressionContext` dataclass SHALL include a `params` field. The `GameTemplateEngine.render()` method SHALL include `params` in the Jinja2 render context dict.

**Reason:** This is a modification to the existing `ExpressionContext` and `GameTemplateEngine.render()` to support custom effect parameter injection.

**Migration:** The `params` field has a `default_factory=dict` default, making it backward compatible. Existing code that constructs `ExpressionContext` without `params` gets an empty dict.

#### Scenario: existing code that doesn't pass params still works

- **GIVEN** existing code that constructs `ExpressionContext(player=..., game=...)` without `params`
- **WHEN** a template is rendered
- **THEN** `params` is an empty dict in the Jinja2 context, and no error occurs

## ADDED Requirements

### Requirement: SkillGrantEffect in the effect union

The effect union (used in adventure steps, item use_effects, and skill use_effects) SHALL include a `skill_grant` effect type. It SHALL have a `skill` field (string, required) naming the Skill manifest to teach. When dispatched by `run_effect()`, it SHALL call `player.grant_skill(skill_ref, registry)`.

#### Scenario: skill_grant effect in adventure step

- **WHEN** an adventure step's effects list includes `{type: skill_grant, skill: fireball}`
- **THEN** after the step runs, `"fireball"` is in `player.known_skills`

#### Scenario: skill_grant with unknown skill ref is rejected at load time

- **WHEN** an adventure manifest includes `{type: skill_grant, skill: nonexistent}` in a step's effects
- **THEN** the content loader raises a validation error

---

### Requirement: DispelEffect and ApplyBuffEffect in the effect union

The effect union SHALL include a `dispel` effect type with a `label: str` field (required, `min_length=1`) and a `target: Literal["player", "enemy"]` field (default `"player"`). When dispatched by `run_effect()` with a `CombatContext`, it SHALL remove all `ActiveCombatEffect` entries from `CombatContext.active_effects` where both `ae.label == label` and `ae.target == target`. When `combat` is `None`, it SHALL be silently skipped.

The effect union SHALL include an `apply_buff` effect type with a `buff_ref: str` field, a `target: Literal["player", "enemy"]` field (default `"player"`), and a `variables: Dict[str, int]` field (default `{}`). `BuffSpec` does NOT carry a `target` field — the target is determined at use time by the `ApplyBuffEffect.target` field, allowing the same buff manifest to be applied to either participant. When dispatched by `run_effect()` with a `CombatContext`, the engine SHALL:

1. Look up the buff in `registry.buffs`.
2. Merge `buff_spec.variables` (defaults) with `effect.variables` (overrides) into `resolved_vars`.
3. For each modifier in `spec.modifiers`, resolve `percent`: if `int`, use directly; if `str`, look up in `resolved_vars`.
4. Construct an `ActiveCombatEffect` with `label=buff_manifest.metadata.name`, `target=effect.target`, and resolved modifier copies, then append it to `combat.active_effects`.

When `combat` is `None`, it SHALL log a WARNING and skip. An unknown `buff_ref` SHALL log an ERROR and skip without crashing.

#### Scenario: dispel dispels a labelled active effect

- **WHEN** `CombatContext.active_effects` contains an `ActiveCombatEffect` with `label="on-fire"` and `target="player"`, and a `dispel` effect with `label="on-fire"` and `target="player"` is dispatched
- **THEN** `CombatContext.active_effects` no longer contains any entry with `label="on-fire"` and `target="player"`

#### Scenario: dispel with no match is a no-op

- **WHEN** a `dispel` effect is dispatched and no active effects match the label
- **THEN** no error is raised and `active_effects` is unchanged

#### Scenario: dispel outside combat is silently skipped

- **WHEN** a `dispel` effect is dispatched with `combat=None`
- **THEN** no error is raised (valid for items used outside combat)

---

## MODIFIED Requirements

### Requirement: Effect dispatcher routes effects to handlers

The effect dispatcher function `run_effect()` SHALL accept all existing parameters plus an optional `combat: CombatContext | None = None` parameter (default None, backward-compatible with all existing call sites).

When `combat` is None and an effect's `target` field is `"enemy"`, the dispatcher SHALL log a WARNING and skip the effect rather than raising an error. This preserves forward-compatibility with content that declares enemy-targeting effects in non-combat contexts.

All existing call sites that do not pass `combat` remain valid and require no updates.

#### Scenario: Existing adventure step effects work without combat parameter

- **WHEN** a stat_change effect runs in a narrative adventure step (no combat)
- **THEN** the effect is dispatched normally without error

#### Scenario: Enemy-targeting effect outside combat is skipped with warning

- **WHEN** a `stat_change` effect with `target: "enemy"` is dispatched with `combat=None`
- **THEN** the effect is skipped, a WARNING is logged, and no other state changes occur

#### Scenario: Enemy-targeting effect inside combat applies to enemy_hp

- **WHEN** a `stat_change` effect with `target: "enemy"` and `amount: -10` is dispatched with a CombatContext where `enemy_hp == 50`
- **THEN** `CombatContext.enemy_hp == 40` after the dispatch

---

## MODIFIED Requirements

### Requirement: target field on StatChangeEffect, StatSetEffect, and HealEffect

`StatChangeEffect` and `HealEffect` SHALL accept a `target: Literal["player", "enemy"]` field (default `"player"`). When `target == "player"`, behavior is identical to the current implementation. When `target == "enemy"`, the effect is routed through `CombatContext.enemy_hp`.

`StatSetEffect` SHALL accept `target: Literal["player"]` only. Declaring `target: "enemy"` on a `stat_set` effect is a load-time validation error.

All existing manifests that omit `target` default to `"player"` and require no changes.

#### Scenario: stat_change with target player is unchanged

- **WHEN** a `stat_change` effect without a `target` field fires
- **THEN** the named stat on the player is modified as before

#### Scenario: heal with target player is unchanged

- **WHEN** a `heal` effect without a `target` field fires
- **THEN** the player's HP is restored as before

#### Scenario: stat_set with target enemy is rejected at load time

- **WHEN** a manifest declares `{type: stat_set, stat: strength, value: 10, target: enemy}`
- **THEN** the content loader raises a validation error

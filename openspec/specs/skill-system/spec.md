# Skill System

## Purpose

The skill system defines the Skill and Buff manifest kinds, skill tracking in character state, the SkillGrantEffect for teaching skills permanently, the SkillCondition predicate for gating content on skill ownership, and optional category governance rules for controlling which skills a character class may learn.

## Requirements

### Requirement: Skill manifest kind

The engine SHALL support a new manifest kind `Skill`. Each Skill manifest SHALL contain a `spec` block with the following fields:

- `displayName` (string, required): human-readable name shown in the TUI.
- `description` (string, optional, default `""`): short flavor or rules text.
- `category` (string, optional, default `""`): organizational label; see CharacterConfig for optional enforcement.
- `contexts` (list of `"combat"` | `"overworld"`, required, at least one entry): declares where the skill may be activated.
- `requires` (Condition, optional): gate evaluated before activation is allowed.
- `cost` (SkillCost, optional): resource deducted each time the skill is used.
- `cooldown` (SkillCooldown, optional): frequency limiter (turn-scope or adventure-scope).
- `use_effects` (list of Effect, optional, default `[]`): immediate effects dispatched on activation. Use `apply_buff` here to grant timed combat buffs by reference to a Buff manifest.

A SkillCost SHALL have `stat` (stat name string) and `amount` (int ≥ 1).
A SkillCooldown SHALL have `scope` (`"turn"` | `"adventure"`) and `count` (int ≥ 1).

To apply a timed combat buff (DoT, shield, amplify, etc.) from a skill, declare an `apply_buff` effect in `use_effects` referencing a `kind: Buff` manifest by name. `SkillSpec` does NOT have a `periodic_effect` field; all buff granting is handled through `ApplyBuffEffect`.

#### Scenario: Minimal skill manifest loads

- **WHEN** a YAML file with `kind: Skill`, a `metadata.name`, and a `spec` containing only `displayName: "Shout"` and `contexts: [combat]` is loaded
- **THEN** the loader parses it without error and registers it in the skill registry

#### Scenario: Skill appears in the registry by its manifest name

- **WHEN** a Skill manifest with `metadata.name: fireball` is loaded
- **THEN** `registry.skills.get("fireball")` returns the loaded manifest

---

### Requirement: Buff manifest kind

The engine SHALL support a `kind: Buff` manifest stored in `oscilla/engine/models/buff.py`. A `BuffSpec` SHALL have `displayName`, `description` (default `""`), `duration_turns` (int ≥ 1), optional `per_turn_effects` (list of Effect, default `[]`), optional `modifiers` (list of CombatModifier, default `[]`), and optional `variables: Dict[str, int]` (default `{}`). `BuffSpec` does **not** have a `target` field — the target is specified on the `ApplyBuffEffect` call site (default `"player"`), allowing the same buff manifest to be applied to either participant. At least one of `per_turn_effects` or `modifiers` MUST be non-empty (validated at load time by `require_tick_or_modifier`).

`CombatModifier.percent` fields accept `int | str`. When a string, it is a variable name that MUST be declared in the owning `BuffSpec.variables` dict (validated at load time by `validate_variable_refs`). At `apply_buff` time the engine resolves all string refs against the merged variables dict (`spec.variables` defaults + `ApplyBuffEffect.variables` overrides) and stores concrete `int` percent values in the resulting `ActiveCombatEffect`.

`CombatModifier` is a discriminated union: `damage_reduction` (percent int/str, valid range 1–99 for int), `damage_amplify` (percent int/str, ≥ 1 for int), `damage_reflect` (percent int/str, 1–100 for int), `damage_vulnerability` (percent int/str, ≥ 1 for int). Each type has a `target` field. Modifiers are passive — read by the combat loop to scale damage arithmetic.

Buff manifests are registered in `ContentRegistry.buffs: KindRegistry[BuffManifest]`.

#### Scenario: Buff manifest with only modifiers loads

- **WHEN** a YAML file with `kind: Buff`, a `metadata.name`, `spec.duration_turns: 3`, and `spec.modifiers: [{type: damage_reduction, percent: 40, target: player}]` is loaded
- **THEN** the loader parses it without error and registers it in `registry.buffs`

#### Scenario: Buff manifest with variable-parameterised modifier loads

- **WHEN** a Buff manifest declares `spec.variables: {reflect_percent: 30}` and a modifier with `percent: reflect_percent`
- **THEN** the loader parses it without error (variable ref is declared)

#### Scenario: Buff manifest references undeclared variable is rejected

- **WHEN** a Buff manifest declares a modifier with `percent: unknown_var` and does not declare `unknown_var` in `spec.variables`
- **THEN** the loader raises a validation error from `validate_variable_refs`

#### Scenario: apply_buff resolves variable to caller override

- **WHEN** a `thorns` buff has `variables: {reflect_percent: 30}` and `modifiers: [{type: damage_reflect, percent: reflect_percent}]`
- **AND** an `apply_buff` effect is dispatched with `variables: {reflect_percent: 60}`
- **THEN** the resulting `ActiveCombatEffect` has a `damage_reflect` modifier with concrete `percent=60`

#### Scenario: apply_buff uses manifest default when no override given

- **WHEN** a `thorns` buff has `variables: {reflect_percent: 30}` and an `apply_buff` effect is dispatched with no `variables` override
- **THEN** the resulting `ActiveCombatEffect` has a `damage_reflect` modifier with concrete `percent=30`

#### Scenario: apply_buff with unknown variable key in override is rejected at load time

- **WHEN** an `apply_buff` effect declares `variables: {bad_key: 99}` and the referenced buff does not declare `bad_key`
- **THEN** the content loader raises a validation error

#### Scenario: Buff manifest with neither per_turn_effects nor modifiers is rejected

- **WHEN** a Buff manifest declares `spec.per_turn_effects: []` and no `modifiers`
- **THEN** the loader raises a validation error from `require_tick_or_modifier`

---

### Requirement: SkillGrantEffect teaches a skill permanently

The `skill_grant` effect type SHALL be added to the discriminated Effect union. When dispatched through `run_effect()`, the engine SHALL call `player.grant_skill(skill_ref, registry)`. If the skill is newly learned, the TUI SHALL display a "learned" notification. If the skill is already known, the effect SHALL be a silent no-op.

#### Scenario: Grant effect teaches a new skill

- **WHEN** a `skill_grant` effect fires for a skill not yet in `player.known_skills`
- **THEN** the skill ref is added to `player.known_skills` and the TUI shows a "You learned:" notification

#### Scenario: Grant effect ignores already-known skill

- **WHEN** a `skill_grant` effect fires for a skill already in `player.known_skills`
- **THEN** no state changes occur and no TUI message is shown

---

### Requirement: CharacterState tracks known skills

`CharacterState` SHALL include:

- `known_skills: Set[str]` — permanently learned skill refs, default empty.
- `skill_cooldowns: Dict[str, int]` — adventure-scope cooldown tracking (skill_ref → adventures remaining before reuse), default empty.
- `available_skills(registry) -> Set[str]` — computed method returning the union of `known_skills`, item-equipped skills, and item-held skills.
- `grant_skill(skill_ref, registry) -> bool` — validates category rules and adds to `known_skills`; returns True if newly learned.
- `tick_skill_cooldowns() -> None` — decrements all adventure-scope cooldowns by one; removes entries that reach zero.

#### Scenario: available_skills with no items returns known_skills

- **WHEN** a player has `known_skills = {"fireball"}` and no items in inventory
- **THEN** `available_skills(registry)` returns `{"fireball"}`

#### Scenario: tick_skill_cooldowns removes expired entries

- **WHEN** `skill_cooldowns = {"fireball": 1}` and `tick_skill_cooldowns()` is called
- **THEN** `"fireball"` is removed from `skill_cooldowns`

#### Scenario: tick_skill_cooldowns decrements remaining count

- **WHEN** `skill_cooldowns = {"icebolt": 3}` and `tick_skill_cooldowns()` is called
- **THEN** `skill_cooldowns["icebolt"] == 2`

---

### Requirement: SkillCondition gates content on skill ownership

The `skill` condition type SHALL be added to the discriminated Condition union. It SHALL have:

- `name` (string, required): skill manifest name to check.
- `mode` (`"available"` | `"learned"`, default `"available"`): determines which skill set is queried.

`mode: "available"` SHALL call `player.available_skills(registry)`.
`mode: "learned"` SHALL check `player.known_skills` only (no registry required).

#### Scenario: Skill condition true when skill is available

- **WHEN** a `skill` condition with `name: fireball, mode: available` is evaluated for a player with `"fireball"` in `available_skills()`
- **THEN** the condition evaluates to true

#### Scenario: Skill condition false when skill not available

- **WHEN** a `skill` condition with `name: fireball, mode: available` is evaluated for a player without `"fireball"` in any source
- **THEN** the condition evaluates to false

#### Scenario: Learned mode ignores item grants

- **WHEN** a `skill` condition with `mode: learned` is evaluated for a player who has `"fireball"` only via an equipped item (not in `known_skills`)
- **THEN** the condition evaluates to false

---

### Requirement: SkillCategoryRules enforce optional governance

`CharacterConfig` MAY declare `skill_category_rules: List[SkillCategoryRule]`. Each rule applies to one `category` string and may declare:

- `max_known` (int ≥ 1 or null): cap on learnable skills in that category.
- `exclusive_with` (list of category strings): categories that conflict with this one.

When `grant_skill()` is called with a registry, the engine SHALL check applicable rules before adding the skill. If a rule blocks the grant, the method SHALL return False without mutating state.

When no rules are declared for a category, no restrictions apply.

#### Scenario: max_known blocks excess skills

- **WHEN** a CharacterConfig has `skill_category_rules: [{category: fire, max_known: 2}]` and a player already knows two fire-category skills
- **THEN** `grant_skill("fireball3")` returns False and `"fireball3"` is not added

#### Scenario: exclusive_with blocks conflicting category

- **WHEN** a CharacterConfig declares fire and ice categories as mutually exclusive and the player already knows a fire skill
- **THEN** `grant_skill("ice-bolt")` (ice category) returns False

#### Scenario: No rules, no governance

- **WHEN** CharacterConfig has no `skill_category_rules`
- **THEN** any skill can be granted without restriction

---

### Requirement: Skill persistence (known_skills and skill_cooldowns)

`known_skills` and `skill_cooldowns` SHALL be included in `to_dict()` and restored in `from_dict()`. The database schema SHALL include a `character_iteration_skills` table (iteration_id, skill_ref as composite PK) and a `character_iteration_skill_cooldowns` table (iteration_id, skill_ref, remaining_adventures) persisted alongside the existing milestone and stat child tables.

Absent keys in saved-game dicts SHALL default to empty (backward-compatible with pre-skill saves).

#### Scenario: Roundtrip preserves known_skills

- **WHEN** a CharacterState with `known_skills = {"fireball", "icebolt"}` is serialized and deserialized
- **THEN** the restored state has `known_skills == {"fireball", "icebolt"}`

#### Scenario: Legacy save without known_skills loads cleanly

- **WHEN** a saved-game dict lacks the `"known_skills"` key
- **THEN** `from_dict()` sets `known_skills = set()` without error

#### Scenario: Skill cooldowns survive save/restore

- **WHEN** a CharacterState with `skill_cooldowns = {"fireball": 2}` is saved and restored
- **THEN** `skill_cooldowns == {"fireball": 2}`

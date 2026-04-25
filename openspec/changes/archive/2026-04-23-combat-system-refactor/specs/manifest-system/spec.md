## ADDED Requirements

### Requirement: CombatSystem entity kind

The manifest system SHALL support the `CombatSystem` kind, which validates against `CombatSystemManifest`. The content registry SHALL store all registered `CombatSystem` manifests and expose them via a dedicated `combat_systems` namespace.

#### Scenario: CombatSystem manifest loaded

- **WHEN** a YAML file with `kind: CombatSystem` and a valid `CombatSystemSpec` is loaded
- **THEN** it is parsed into `CombatSystemManifest` and registered under `combat_systems`

---

## MODIFIED Requirements

### Requirement: Supported entity kinds

The manifest system SHALL support the following `kind` values: `Region`, `Location`, `Adventure`, `Enemy`, `Item`, `Recipe`, `Quest`, `Archetype`, `Game`, `CharacterConfig`, `Skill`, `Buff`, `LootTable`, and `CombatSystem`.

#### Scenario: CombatSystem maps to CombatSystemManifest

- **WHEN** a manifest with `kind: CombatSystem` is loaded
- **THEN** it is validated against `CombatSystemManifest` and stored in `registry.combat_systems`

---

### Requirement: EnemySpec declares stats as a dict

The `Enemy` manifest's `spec` SHALL declare `stats: Dict[str, int]` (fully author-defined stat names and values) and `on_defeat_effects: List[Effect]` (effects run when the enemy is defeated — used for XP grants, milestone awards, or any other reward). The fixed fields `hp`, `attack`, `defense`, and `xp_reward` are removed. This is a breaking change for all existing enemy manifests.

#### Scenario: Enemy manifest with stats dict loads successfully

- **WHEN** an enemy manifest declares `spec.stats: {hp: 50, attack: 8, defense: 3}` and `spec.on_defeat_effects: []`
- **THEN** it parses into `EnemySpec` without error and `enemy.spec.stats["hp"]` is 50

#### Scenario: Enemy manifest with legacy fields rejected

- **WHEN** an enemy manifest declares the legacy `spec.hp` field
- **THEN** the content loader raises a `ValidationError` identifying the unrecognised field

---

### Requirement: CombatStep carries system selection and overrides

The `combat` step in an adventure manifest SHALL accept an optional `combat_system: str` field that names a specific `CombatSystem` manifest to use for that encounter, and an optional `combat_overrides: CombatStepOverrides` field that overrides any `CombatSystemSpec` fields for that encounter only.

#### Scenario: CombatStep with explicit system name

- **WHEN** a `combat` step declares `combat_system: "boss-fight"` and that manifest is registered
- **THEN** the boss-fight system governs that encounter instead of the game default

#### Scenario: CombatStep with overrides

- **WHEN** a `combat` step declares `combat_overrides: {turn_order: "enemy_first"}`
- **THEN** only the turn order is overridden for that encounter; all other system fields remain from the default

---

### Requirement: SkillSpec contexts is an open string list

The `contexts` field on `SkillSpec` SHALL be a `List[str]` of arbitrary strings (not a fixed enum). The value `"overworld"` remains a reserved built-in context that controls overworld availability. Additional context values are declared by `CombatSystem` manifests via their `skill_contexts` list. A skill is eligible in a combat system when its `contexts` list intersects the system's `skill_contexts`.

#### Scenario: Skill with custom context eligible in matching combat system

- **WHEN** a `Skill` manifest declares `contexts: ["tactical"]` and a `CombatSystem` declares `skill_contexts: ["tactical"]`
- **THEN** that skill appears in the choice-mode menu for that combat system

#### Scenario: Skill with overworld context only is not eligible in combat

- **WHEN** a `Skill` manifest declares only `contexts: ["overworld"]`
- **THEN** it does not appear in any combat system's choice-mode menu

---

### Requirement: SkillSpec carries combat damage formulas

`SkillSpec` SHALL accept an optional `combat_damage_formulas: List[DamageFormulaEntry]` field. These formulas are rendered in `CombatFormulaContext` when the skill is used as a move in `"choice"` mode; a single skill can target multiple enemy vitals in one turn.

#### Scenario: Skill with combat_damage_formulas applies damage when used in combat

- **WHEN** a player selects a skill with `combat_damage_formulas` in a choice-mode combat
- **THEN** the declared formulas are rendered and the results are applied to the appropriate stat namespaces

---

### Requirement: ItemSpec and EquipSpec carry combat fields

`ItemSpec` SHALL accept `contexts: List[str] = []` (same open-string semantics as `SkillSpec.contexts`) and `combat_damage_formulas: List[DamageFormulaEntry] = []`. `EquipSpec` SHALL accept `combat_damage_formulas: List[DamageFormulaEntry] = []`. Context-scoped items appear as choice-mode actions; equip formulas fire automatically each round in auto mode.

#### Scenario: Item with combat context eligible as combat action

- **WHEN** an `Item` manifest declares `contexts: ["combat"]` and the current `CombatSystem` has `skill_contexts: ["combat"]`
- **THEN** the item appears as an action in the choice-mode menu

---

### Requirement: GameSpec carries default combat system reference

`GameSpec` SHALL accept an optional `default_combat_system: str | None = None` field. When set, the named `CombatSystem` manifest is used as the default for all `combat` steps that do not declare their own `combat_system` field.

#### Scenario: GameSpec default_combat_system used when step has no explicit system

- **WHEN** `GameSpec.default_combat_system: "standard-combat"` and a `combat` step has no `combat_system` field
- **THEN** the standard-combat system is used for that encounter

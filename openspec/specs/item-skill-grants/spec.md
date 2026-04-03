# Item Skill Grants

## Purpose

The item skill grants system enables items to extend a player's available skill set — either while equipped in a slot or while held anywhere in the inventory — without permanently teaching those skills to the character.

## Requirements

### Requirement: Items grant skills while equipped

`ItemSpec` SHALL accept a `grants_skills_equipped: List[str]` field (default `[]`). Each string is a Skill manifest name. Skills in this list SHALL be included in `player.available_skills(registry)` if and only if the item is currently occupying an equipment slot. Unequipping the item SHALL immediately remove those skills from `available_skills()`. The skills are NOT added to `player.known_skills`.

Only items with an `equip` spec may meaningfully use `grants_skills_equipped`; the field is not validated against the presence of an `equip` spec, but skills will never appear in `available_skills()` for unequippable items since they can never be equipped.

#### Scenario: Equipped staff grants a spell

- **WHEN** a player equips a staff item with `grants_skills_equipped: ["arcane-blast"]`
- **THEN** `player.available_skills(registry)` includes `"arcane-blast"`

#### Scenario: Unequipping staff removes the grant

- **WHEN** the player previously had the staff equipped and then removes it from the slot
- **THEN** `player.available_skills(registry)` no longer includes `"arcane-blast"`

#### Scenario: Equipped skill is not in known_skills

- **WHEN** a player uses a SkillCondition with `mode: learned` for a skill only granted by an equipped item
- **THEN** the condition evaluates to false (the skill is available but not learned)

---

### Requirement: Items grant skills while held in inventory

`ItemSpec` SHALL accept a `grants_skills_held: List[str]` field (default `[]`). Each string is a Skill manifest name. Skills in this list SHALL be included in `player.available_skills(registry)` if the item appears anywhere in the player's inventory — either as stacks (quantity ≥ 1) or as item instances — regardless of whether it occupies an equipment slot. Removing the last instance/stack of the item removes the grants.

#### Scenario: Holding a scroll grants a spell

- **WHEN** a player has a "fireball-scroll" item in their stacks with `grants_skills_held: ["fireball"]`
- **THEN** `player.available_skills(registry)` includes `"fireball"`

#### Scenario: Consuming the last scroll removes the grant

- **WHEN** the player uses and consumes the last fireball-scroll
- **THEN** `player.available_skills(registry)` no longer includes `"fireball"` (assuming it's not in known_skills)

#### Scenario: Item instance grants a held-skill

- **WHEN** a player has a non-stackable item instance in their inventory with `grants_skills_held: ["intimidate"]`
- **THEN** `player.available_skills(registry)` includes `"intimidate"`

---

### Requirement: available_skills computes union from all sources

`CharacterState.available_skills(registry)` SHALL return the union of:

1. All entries in `player.known_skills`.
2. Skills from `grants_skills_equipped` for items currently in an equipment slot.
3. Skills from `grants_skills_held` for all items in stacks or instances (equipped or not).
4. Skills from `skill_grants` of any `PassiveEffect` in `GameSpec.passive_effects` whose condition evaluates true when checked against base stats (`registry=None`).

Without a registry, only `known_skills` is returned. The method SHALL accept `registry=None` and degrade gracefully. Passive effect conditions that require a registry (e.g., `item_held_label`, `any_item_equipped`) will return false when evaluated inside `available_skills()` because passive conditions are always evaluated without a registry to prevent circular evaluation; authors should prefer using `item_equipped` (which does not require a registry at that level) in passive conditions that gate skill grants.

#### Scenario: available_skills union from multiple sources including passive effect

- **WHEN** a player has `known_skills = {"shout"}`, equips a sword with `grants_skills_equipped: ["power-strike"]`, holds a potion with `grants_skills_held: ["detect-poison"]`, and a passive effect with `skill_grants: ["endure"]` whose condition is currently true
- **THEN** `available_skills(registry)` returns `{"shout", "power-strike", "detect-poison", "endure"}`

#### Scenario: available_skills without registry returns only known_skills

- **WHEN** `registry=None` is passed to `available_skills()`
- **THEN** the return value equals `player.known_skills`

#### Scenario: Passive skill grant removed when condition no longer true

- **WHEN** a passive effect's condition was true (skill was in `available_skills`) and something changes to make the condition false
- **THEN** `available_skills(registry)` no longer includes the passive-granted skill

---

### Requirement: Skill refs in items are validated at load time

All skill refs in `grants_skills_equipped` and `grants_skills_held` SHALL be validated against the set of loaded Skill manifest names by the content loader. Unknown refs SHALL cause a load-time error.

#### Scenario: Unknown skill ref in item is rejected

- **WHEN** an Item manifest declares `grants_skills_equipped: ["nonexistent-skill"]` and no Skill manifest with that name exists
- **THEN** the content loader raises a validation error naming the item and the unknown ref

#### Scenario: Valid skill refs load cleanly

- **WHEN** all skill refs in an item's `grants_skills_equipped` and `grants_skills_held` correspond to loaded Skill manifests
- **THEN** the content loader accepts the item manifest without error

---

### Requirement: Items grant buffs at combat start while equipped or held

`ItemSpec` SHALL accept `grants_buffs_equipped: List[BuffGrant]` and `grants_buffs_held: List[BuffGrant]` fields (both default `[]`). `BuffGrant` is a Pydantic model with `buff_ref: str` and `variables: Dict[str, int] = {}`. The `variables` dict MAY override any key declared in the referenced `BuffSpec.variables`; unknown keys SHALL cause a load-time error.

At the start of each `run_combat()` call, before round 1, the engine SHALL dispatch an `ApplyBuffEffect` for each `BuffGrant` in `grants_buffs_equipped` of equipped items and for each `BuffGrant` in `grants_buffs_held` of any held item (stacks or instances), passing `grant.buff_ref`, `target="player"`, and `grant.variables`. This uses the same `apply_buff` path as skills and adventures — the Buff manifest is looked up once and an `ActiveCombatEffect` is appended to `CombatContext.active_effects`.

Unlike `grants_skills_equipped`/`held`, which provide skills that persist across the entire combat, `grants_buffs_equipped`/`held` produce `ActiveCombatEffect` entries that tick down and expire according to `BuffSpec.duration_turns`. The buff is re-applied fresh at the start of every combat.

Unknown buff refs are logged as errors and skipped; they do not prevent combat from starting.

#### Scenario: Equipped weapon grants buff at combat start

- **WHEN** a player equips a `thorns-sword` with `grants_buffs_equipped: [{buff_ref: thorns}]`
- **AND** a Buff manifest named `"thorns"` exists in the registry
- **THEN** at the start of combat, `CombatContext.active_effects` contains an entry with `label="thorns"` before round 1

#### Scenario: Equipped item grants buff with variable override

- **WHEN** a player equips a `master-thorns-sword` with `grants_buffs_equipped: [{buff_ref: thorns, variables: {reflect_percent: 60}}]`
- **AND** the `thorns` Buff manifest has `variables: {reflect_percent: 30}` and a `damage_reflect` modifier referencing `reflect_percent`
- **THEN** the resulting `ActiveCombatEffect` has a `damage_reflect` modifier with concrete `percent=60`

#### Scenario: Held item grants buff at combat start without being equipped

- **WHEN** a player carries a `guardian-charm` with `grants_buffs_held: [{buff_ref: shielded}]` (not equipped)
- **AND** a Buff manifest named `"shielded"` exists in the registry
- **THEN** at the start of combat, `CombatContext.active_effects` contains an entry with `label="shielded"` before round 1

---

### Requirement: Buff refs in items are validated at load time

All buff refs in `grants_buffs_equipped` and `grants_buffs_held` SHALL be validated against the set of loaded Buff manifest names by the content loader. Unknown refs SHALL cause a load-time error. Variable override keys that are not declared in the referenced `BuffSpec.variables` SHALL also cause a load-time error.

#### Scenario: Unknown buff ref in item is rejected at load

- **WHEN** an Item manifest declares `grants_buffs_equipped: [{buff_ref: nonexistent-buff}]` and no Buff manifest with that name exists
- **THEN** the content loader raises a validation error naming the item and the unknown ref

#### Scenario: Unknown variable key in buff grant is rejected at load

- **WHEN** an Item manifest declares `grants_buffs_equipped: [{buff_ref: thorns, variables: {bad_key: 60}}]` and `thorns` does not declare `bad_key` in its `variables`
- **THEN** the content loader raises a validation error naming the item and the unknown key

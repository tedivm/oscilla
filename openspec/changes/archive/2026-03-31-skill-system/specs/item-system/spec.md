## ADDED Requirements

### Requirement: ItemSpec declares skill grants for equipped items

`ItemSpec` SHALL accept `grants_skills_equipped: List[str]` (default `[]`). Each entry is a Skill manifest name. Grants are ephemeral: the skills enter `available_skills()` only while the item occupies an equipment slot. These are NOT added to `known_skills`.

#### Scenario: Equipped item contributes to available_skills

- **WHEN** a player equips an item with `grants_skills_equipped: ["power-strike"]`
- **THEN** `available_skills(registry)` includes `"power-strike"`

#### Scenario: Unequipped item no longer contributes

- **WHEN** a player removes an equipped item from its slot
- **THEN** skills from `grants_skills_equipped` are no longer in `available_skills()`

---

### Requirement: ItemSpec declares skill grants for held items

`ItemSpec` SHALL accept `grants_skills_held: List[str]` (default `[]`). Each entry is a Skill manifest name. Grants are active when the item is present anywhere in the player's inventory (stacks quantity ≥ 1 or any instance), whether equipped or not. Consuming or dropping the last copy removes the grant.

#### Scenario: Held scroll adds skill without equipping

- **WHEN** a player holds a scroll in their stacks with `grants_skills_held: ["fireball"]`
- **THEN** `available_skills(registry)` includes `"fireball"` without equipping it

#### Scenario: Consuming last scroll removes skill from available_skills

- **WHEN** a player uses and consumes the last instance of a scroll that was granting a skill
- **THEN** the skill is no longer in `available_skills()`

---

### Requirement: Skill refs in items are validated at load time

All skill refs in `grants_skills_equipped` and `grants_skills_held` SHALL be validated against loaded Skill manifest names at content load time. Unknown refs SHALL cause a load-time error.

#### Scenario: Unknown skill ref is rejected

- **WHEN** an Item manifest references a skill ref that has no corresponding Skill manifest
- **THEN** the content loader raises a validation error identifying the item and ref

#### Scenario: Valid skill refs load cleanly

- **WHEN** all skill refs in an item manifest correspond to loaded Skill manifests
- **THEN** the item loads without error

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Player state includes known_skills and skill_cooldowns

`CharacterState` SHALL include:

- `known_skills: Set[str]` — permanently learned skill refs, default empty set.
- `skill_cooldowns: Dict[str, int]` — adventure-scope cooldown map (skill_ref → adventures remaining before reuse), default empty dict.

Both fields SHALL be included in `to_dict()` serialization and restored by `from_dict()`. Keys absent from a saved-game dict SHALL default to empty without error, ensuring backward compatibility with pre-skill saves.

#### Scenario: New player starts with empty known_skills and skill_cooldowns

- **WHEN** a new character is created
- **THEN** `player.known_skills == set()` and `player.skill_cooldowns == {}`

#### Scenario: known_skills survives serialization roundtrip

- **WHEN** a player with `known_skills = {"fireball"}` is serialized via `to_dict()` and restored via `from_dict()`
- **THEN** the restored player has `known_skills == {"fireball"}`

#### Scenario: skill_cooldowns survive serialization roundtrip

- **WHEN** a player with `skill_cooldowns = {"fireball": 2}` is serialized and restored
- **THEN** the restored player has `skill_cooldowns == {"fireball": 2}`

#### Scenario: Missing keys in saved dict default to empty

- **WHEN** `from_dict()` is called with a dict that has no `"known_skills"` or `"skill_cooldowns"` keys
- **THEN** the player initializes with `known_skills = set()` and `skill_cooldowns = {}`

---

### Requirement: available_skills returns computed union

`CharacterState` SHALL expose `available_skills(registry=None) -> Set[str]`. This method SHALL return the union of:

1. `known_skills`.
2. Skills from `grants_skills_equipped` for currently equipped items.
3. Skills from `grants_skills_held` for all items in stacks or instances.

When registry is None, only `known_skills` is returned.

#### Scenario: Union from all three sources

- **WHEN** a player has a known skill, an equipped-skill from their weapon, and a held-skill from a scroll
- **THEN** `available_skills(registry)` contains all three skill refs

#### Scenario: No registry returns known_skills only

- **WHEN** `available_skills(None)` is called
- **THEN** the return value equals `player.known_skills`

---

### Requirement: Persistence stores known_skills and skill_cooldowns in the database

The database schema SHALL include:

- `character_iteration_skills` table: composite PK `(iteration_id, skill_ref)`.
- `character_iteration_skill_cooldowns` table: composite PK `(iteration_id, skill_ref)` with `remaining_adventures: int`.

These tables SHALL be populated and read by the character persistence service alongside existing stat and milestone tables. The migration SHALL be purely additive (no existing tables modified).

#### Scenario: Learned skill persists across sessions

- **WHEN** a player learns a skill, and the character is saved and loaded from the database
- **THEN** the skill appears in `known_skills` after load

#### Scenario: Active cooldown persists across sessions

- **WHEN** a player has `skill_cooldowns = {"fireball": 2}`, saves, and reloads
- **THEN** `skill_cooldowns == {"fireball": 2}` after load

#### Scenario: No skill rows in DB returns empty known_skills

- **WHEN** a character has no rows in `character_iteration_skills`
- **THEN** `player.known_skills == set()` after load

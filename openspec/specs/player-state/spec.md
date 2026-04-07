# Player State

## Purpose

The player state system manages all persistent player data including stats, inventory, progression, and adventure position tracking.

## Requirements

### Requirement: Player state fields

The player state model SHALL include the following fixed fields: `player_id` (UUID), `name` (string), `character_class` (string, nullable), `level` (int, default 1), `xp` (int, default 0), `hp` (int), `max_hp` (int), `prestige_count` (int, default 0), `current_location` (string reference, nullable), `milestones` (set of strings), `statistics` (PlayerStatistics dataclass with enemy/location/adventure counters), `stacks` (mapping of item ref to quantity for stackable items), `instances` (list of `ItemInstance` objects for non-stackable items, each with `instance_id: UUID`, `item_ref: str`, and `modifiers: Dict`), `equipment` (mapping of slot name to `instance_id: UUID`), `active_quests` (mapping of quest ref to stage name), `completed_quests` (set of quest refs), `active_adventure` (nullable adventure position struct), `pending_triggers` (FIFO list of trigger names awaiting drain, default empty list), and `prestige_pending` (nullable `PrestigeCarryForward` dataclass, default `None` — see prestige-system spec).

The `prestige_pending` field is ephemeral: it is never serialized to the database or restored from it. It exists solely to signal the `adventure_end` persist path that a prestige iteration transition must be executed before writing the reset state. After the transition, the field is cleared to `None`.

In addition to fixed fields, the player state SHALL contain a `stats` mapping (stat name → value) populated dynamically from the `CharacterConfig` manifest at character creation. Both `public_stats` and `hidden_stats` are stored in this single mapping; the distinction is only presentational. Stat values SHALL be typed `int | bool | None` — the `float` type is no longer permitted. Stat values SHALL default to the declared default, or `null` if no default is set. Integer stats SHALL only be mutated through `CharacterState.set_stat()`, which enforces hard INT32 floor/ceiling bounds.

#### Scenario: New player starts with default values

- **WHEN** a new player state is created with only a name
- **THEN** level is 1, XP is 0, prestige_count is 0, milestones is empty, statistics has all counters at zero, stacks is empty, instances is empty, equipment is empty, active_adventure is None, pending_triggers is an empty list, prestige_pending is None, and the stats map contains every stat from CharacterConfig initialised to its declared default

#### Scenario: Public stats are visible, hidden stats are not

- **WHEN** the player status panel is rendered
- **THEN** only stats declared under `public_stats` in CharacterConfig are displayed; stats in `hidden_stats` are omitted from the UI

#### Scenario: Stats map contains only int and bool values

- **WHEN** a character is created from a `CharacterConfig` that declares only `int` and `bool` stats
- **THEN** every value in `player.stats` is an `int`, `bool`, or `None`; no `float` values are present

#### Scenario: prestige_pending is ephemeral — not in to_dict output

- **WHEN** `player.to_dict()` is called while `prestige_pending` is not None
- **THEN** the returned dict does not contain a `prestige_pending` key

#### Scenario: prestige_pending survives in-memory until adventure_end

- **WHEN** the prestige effect fires mid-adventure and sets `prestige_pending`
- **THEN** subsequent steps in the same adventure observe `prestige_pending is not None` on the in-memory state
- **AND THEN** `prestige_pending` is `None` after `_persist_diff(event="adventure_end")` completes

---

### Requirement: Inventory management

The player state SHALL maintain two separate inventory collections: `stacks: Dict[str, int]` for stackable items (item_ref → quantity) and `instances: List[ItemInstance]` for non-stackable items tracked by UUID. `add_item()` routes to the appropriate collection based on the item's `stackable` flag in the registry. Removing a stackable item when quantity would go below zero SHALL raise an error. Attempting to add a non-stackable item with quantity != 1 SHALL raise an error.

#### Scenario: Adding a stackable item

- **WHEN** `add_item("healing-potion", 1)` is called and `healing-potion` has `stackable: true`
- **THEN** `stacks["healing-potion"]` increases by 1

#### Scenario: Adding a non-stackable item

- **WHEN** `add_item("iron-sword", 1)` is called and `iron-sword` has `stackable: false`
- **THEN** a new `ItemInstance` with a fresh UUID is appended to `instances`

#### Scenario: Removing a stackable item

- **WHEN** `remove_item("healing-potion", 1)` is called on a player who has 2 healing-potions
- **THEN** `stacks["healing-potion"]` is 1

#### Scenario: Removing more than available raises error

- **WHEN** `remove_item("healing-potion", 5)` is called on a player who has only 1
- **THEN** a ValueError is raised and stacks is unchanged

---

### Requirement: Milestone management

The player state SHALL support granting a milestone (adding to the set) and querying whether a milestone is present. Granting an already-held milestone SHALL be a no-op.

#### Scenario: Granting a new milestone

- **WHEN** `grant_milestone("found-the-map")` is called on a player without that milestone
- **THEN** the milestone is added to the player's milestone set

#### Scenario: Querying a present milestone

- **WHEN** `has_milestone("found-the-map")` is called for a player who has it
- **THEN** it returns True

---

### Requirement: Statistics tracking

The player state SHALL maintain a `statistics` field of type `PlayerStatistics` containing three independent counter mappings: `enemies_defeated` (enemy manifest name → int), `locations_visited` (location manifest name → int), and `adventures_completed` (adventure manifest name → int). All counters SHALL default to 0 when absent (missing keys are equivalent to 0 and SHALL never raise a KeyError).

The engine SHALL automatically increment these counters as follows:

- `enemies_defeated[enemy_ref]` increments by 1 when a `combat` step ends in player victory.
- `locations_visited[location_ref]` increments by 1 each time the player enters a location to select an adventure.
- `adventures_completed[adventure_ref]` increments by 1 when an adventure pipeline runs to full completion (all steps resolved; not on flee or defeat).

Counters are append-only and SHALL never be decremented. All three counter categories are available as condition tree leaves (`enemies_defeated`, `locations_visited`, `adventures_completed`) so content authors can gate content on kill counts, visit history, and run completion counts.

#### Scenario: Enemy defeat increments counter

- **WHEN** a combat step ends with the player defeating `goblin-scout`
- **THEN** `statistics.enemies_defeated["goblin-scout"]` increases by 1

#### Scenario: Repeated visits accumulate

- **WHEN** a player visits `village-square` three times across three separate adventure selections
- **THEN** `statistics.locations_visited["village-square"]` is 3

#### Scenario: Incomplete adventure does not count

- **WHEN** a player flees from an adventure mid-way
- **THEN** `statistics.adventures_completed` is not incremented for that adventure

#### Scenario: Fresh player has all counters at zero

- **WHEN** a new player state is created
- **THEN** all three counter dicts in `statistics` are empty (querying any key returns 0)

---

### Requirement: XP and levelling

The player state SHALL track XP and level. XP thresholds per level SHALL be defined in the game manifest (default formula if not specified). When XP is added that crosses a level threshold, the level SHALL increment automatically. A level-up SHALL also recalculate max_hp and stat caps if defined.

#### Scenario: XP added below threshold

- **WHEN** 50 XP is added and it does not cross the next level threshold
- **THEN** XP increases and level remains unchanged

#### Scenario: XP crosses level threshold

- **WHEN** XP is added and the cumulative total crosses the threshold for level 2
- **THEN** level increments to 2 and max_hp is recalculated

---

### Requirement: Active adventure position

The player state SHALL include an `active_adventure` field that stores the current adventure reference, the current step index, and a step-local state dict for mid-step persistence (e.g., enemy HP in a combat step). When no adventure is running `active_adventure` SHALL be None.

#### Scenario: Adventure position is set when adventure starts

- **WHEN** an adventure begins
- **THEN** `active_adventure` is set with the adventure ref, step index 0, and empty step state

#### Scenario: Adventure position is cleared when adventure ends

- **WHEN** an adventure ends (completion, defeat, or flee)
- **THEN** `active_adventure` is reset to None

---

### Requirement: Equipment slots

The player state SHALL support equipping a non-stackable item instance to one or more named slots. Equipment is tracked as `equipment: Dict[str, UUID]` mapping slot name to `instance_id`. Equipping an item instance to a slot already occupied by a different instance SHALL displace the existing instance (returning it to `instances`). Equipment slot definitions (names, accepted categories, unlock conditions) live in `CharacterConfig.equipment_slots`.

Equipping is only available outside adventures. Inside adventures, only item consumption (via `UseItemEffect`) is permitted.

#### Scenario: Equip an item instance

- **WHEN** `equip_instance(instance_id, slots=["main_hand"])` is called and the instance is in `instances`
- **THEN** `equipment["main_hand"]` is set to `instance_id` and the instance remains in `instances` (equipped items stay in `instances`; `equipment` is an index into `instances`)

#### Scenario: Equip displaces existing item

- **WHEN** a new weapon instance is equipped to `main_hand` while another instance already occupies `main_hand`
- **THEN** the displaced instance remains in `instances` (unequipped) and `equipment["main_hand"]` points to the new instance

#### Scenario: Multi-slot item occupies all declared slots

- **WHEN** a two-handed sword with `slots: [main_hand, off_hand]` is equipped
- **THEN** both `equipment["main_hand"]` and `equipment["off_hand"]` point to the same `instance_id`

---

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

---

### Requirement: prestige_count serialized as prestige_count key

The `CharacterState.to_dict()` method SHALL serialize the prestige run counter under the key `"prestige_count"`. The `CharacterState.from_dict()` method SHALL read from `"prestige_count"`, falling back to the legacy `"iteration"` key for backward compatibility with any serialized states created before this change.

#### Scenario: to_dict uses prestige_count key

- **WHEN** `player.to_dict()` is called on any character state
- **THEN** the returned dict contains the key `"prestige_count"` with the integer value and does not contain the key `"iteration"`

#### Scenario: from_dict reads prestige_count key

- **WHEN** `CharacterState.from_dict({"prestige_count": 3, ...})` is called
- **THEN** the resulting state has `prestige_count == 3`

#### Scenario: from_dict accepts legacy iteration key

- **WHEN** `CharacterState.from_dict({"iteration": 2, ...})` is called (no prestige_count key)
- **THEN** the resulting state has `prestige_count == 2` (legacy key accepted for backward compat)

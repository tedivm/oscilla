# Player State

## Purpose

The player state system manages all persistent player data including stats, inventory, progression, and adventure position tracking.

## Requirements

### Requirement: Player state fields

The player state model SHALL include the following fixed fields: `player_id` (UUID), `name` (string), `character_class` (string, nullable), `level` (int, default 1), `xp` (int, default 0), `hp` (int), `max_hp` (int), `prestige_count` (int, default 0), `current_location` (string reference, nullable), `milestones` (set of strings), `statistics` (PlayerStatistics dataclass with enemy/location/adventure counters), `stacks` (mapping of item ref to quantity for stackable items), `instances` (list of `ItemInstance` objects for non-stackable items, each with `instance_id: UUID`, `item_ref: str`, and `modifiers: Dict`), `equipment` (mapping of slot name to `instance_id: UUID`), `active_quests` (mapping of quest ref to stage name), `completed_quests` (set of quest refs), and `active_adventure` (nullable adventure position struct).

In addition to fixed fields, the player state SHALL contain a `stats` mapping (stat name → value) populated dynamically from the `CharacterConfig` manifest at character creation. Both `public_stats` and `hidden_stats` are stored in this single mapping; the distinction is only presentational. Stat values SHALL be typed `int | bool | None` — the `float` type is no longer permitted. Stat values SHALL default to the declared default, or `null` if no default is set. Integer stats SHALL only be mutated through `CharacterState.set_stat()`, which enforces hard INT32 floor/ceiling bounds.

#### Scenario: New player starts with default values

- **WHEN** a new player state is created with only a name
- **THEN** level is 1, XP is 0, prestige_count is 0, milestones is empty, statistics has all counters at zero, stacks is empty, instances is empty, equipment is empty, active_adventure is None, and the stats map contains every stat from CharacterConfig initialised to its declared default

#### Scenario: Public stats are visible, hidden stats are not

- **WHEN** the player status panel is rendered
- **THEN** only stats declared under `public_stats` in CharacterConfig are displayed; stats in `hidden_stats` are omitted from the UI

#### Scenario: Stats map contains only int and bool values

- **WHEN** a character is created from a `CharacterConfig` that declares only `int` and `bool` stats
- **THEN** every value in `player.stats` is an `int`, `bool`, or `None`; no `float` values are present

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

# Player State

## Purpose

The player state system manages all persistent player data including stats, inventory, progression, and adventure position tracking.

## Requirements

### Requirement: Player state fields

The player state model SHALL include the following fixed fields: `player_id` (UUID), `name` (string), `character_class` (string, nullable), `level` (int, default 1), `xp` (int, default 0), `hp` (int), `max_hp` (int), `prestige_count` (int, default 0), `current_location` (string reference, nullable), `milestones` (set of strings), `statistics` (PlayerStatistics dataclass with enemy/location/adventure counters), `inventory` (mapping of item ref to quantity), `equipment` (mapping of slot name to item ref), `active_quests` (mapping of quest ref to stage name), `completed_quests` (set of quest refs), and `active_adventure` (nullable adventure position struct).

In addition to fixed fields, the player state SHALL contain a `stats` mapping (stat name → value) populated dynamically from the `CharacterConfig` manifest at character creation. Both `public_stats` and `hidden_stats` are stored in this single mapping; the distinction is only presentational. Stat values SHALL be typed according to the `CharacterConfig` definition and SHALL default to the declared default, or `null` if no default is set.

#### Scenario: New player starts with default values

- **WHEN** a new player state is created with only a name
- **THEN** level is 1, XP is 0, prestige_count is 0, milestones is empty, statistics has all counters at zero, inventory is empty, equipment is empty, active_adventure is None, and the stats map contains every stat from CharacterConfig initialised to its declared default

#### Scenario: Public stats are visible, hidden stats are not

- **WHEN** the player status panel is rendered
- **THEN** only stats declared under `public_stats` in CharacterConfig are displayed; stats in `hidden_stats` are omitted from the UI

---

### Requirement: Inventory management

The player state SHALL support adding items (incrementing quantity), removing items (decrementing quantity), and querying whether a specific item is present (quantity > 0). Removing an item when quantity would go below zero SHALL raise an error.

#### Scenario: Adding an item

- **WHEN** `add_item("iron-sword", 1)` is called on a player who has no iron-sword
- **THEN** inventory contains `{"iron-sword": 1}`

#### Scenario: Removing an item

- **WHEN** `remove_item("iron-sword", 1)` is called on a player who has 2 iron-swords
- **THEN** inventory contains `{"iron-sword": 1}`

#### Scenario: Removing more than available raises error

- **WHEN** `remove_item("iron-sword", 5)` is called on a player who has only 1
- **THEN** a ValueError is raised and inventory is unchanged

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

The player state SHALL support equipping an item to a named slot (e.g., `weapon`, `armor`, `accessory`). Equipping an item to an occupied slot SHALL replace the previous item (returning it to inventory). Equipping requires the item to be in inventory.

#### Scenario: Equip an item

- **WHEN** `equip("iron-sword", slot="weapon")` is called and the player has iron-sword in inventory
- **THEN** the weapon slot contains iron-sword and iron-sword is removed from inventory

#### Scenario: Equip replaces existing item

- **WHEN** a weapon is already equipped and a new weapon is equipped to the same slot
- **THEN** the old weapon is returned to inventory and the slot contains the new weapon

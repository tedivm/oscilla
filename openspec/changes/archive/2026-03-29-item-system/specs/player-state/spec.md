# Player State (delta)

## MODIFIED Requirements

### Requirement: Player state fields

> **Changed by this change**: The inventory and equipment fields are restructured. The old `inventory: Dict[str, int]` field is replaced by `stacks: Dict[str, int]` (stackable items) and `instances: List[ItemInstance]` (non-stackable items). The `equipment` field changes from `Dict[str, str]` (slot → item_ref) to `Dict[str, UUID]` (slot → instance_id).

The player state model SHALL include the following fixed fields: `player_id` (UUID), `name` (string), `character_class` (string, nullable), `level` (int, default 1), `xp` (int, default 0), `hp` (int), `max_hp` (int), `prestige_count` (int, default 0), `current_location` (string reference, nullable), `milestones` (set of strings), `statistics` (PlayerStatistics dataclass with enemy/location/adventure counters), `stacks` (mapping of item ref to quantity for stackable items), `instances` (list of `ItemInstance` objects for non-stackable items, each with `instance_id: UUID`, `item_ref: str`, and `modifiers: Dict`), `equipment` (mapping of slot name to `instance_id: UUID`), `active_quests` (mapping of quest ref to stage name), `completed_quests` (set of quest refs), and `active_adventure` (nullable adventure position struct).

In addition to fixed fields, the player state SHALL contain a `stats` mapping (stat name → value) populated dynamically from the `CharacterConfig` manifest at character creation. Both `public_stats` and `hidden_stats` are stored in this single mapping; the distinction is only presentational. Stat values SHALL be typed according to the `CharacterConfig` definition and SHALL default to the declared default, or `null` if no default is set.

#### Scenario: New player starts with default values

- **WHEN** a new player state is created with only a name
- **THEN** level is 1, XP is 0, prestige_count is 0, milestones is empty, statistics has all counters at zero, stacks is empty, instances is empty, equipment is empty, active_adventure is None, and the stats map contains every stat from CharacterConfig initialised to its declared default

---

### Requirement: Inventory management

> **Changed by this change**: The single `inventory: Dict[str, int]` collection is replaced by two separate collections — `stacks` for stackable items and `instances` for non-stackable items — routed by the item's `stackable` flag.

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

### Requirement: Equipment slots

> **Changed by this change**: The `equipment` field type changes from `Dict[str, str]` (slot → item_ref) to `Dict[str, UUID]` (slot → instance_id). Equipment is now keyed by the unique `instance_id` of a non-stackable `ItemInstance` rather than by item manifest name.

The player state SHALL support equipping a non-stackable item instance to one or more named slots. Equipment is tracked as `equipment: Dict[str, UUID]` mapping slot name to `instance_id`. Equipping an item instance to a slot already occupied by a different instance SHALL displace the existing instance (it remains in `instances` as unequipped). Equipment slot definitions (names, accepted categories, unlock conditions) live in `CharacterConfig.equipment_slots`.

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

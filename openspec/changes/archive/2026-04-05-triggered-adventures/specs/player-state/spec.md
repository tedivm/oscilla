## MODIFIED Requirements

### Requirement: Player state fields

The player state model SHALL include the following fixed fields: `player_id` (UUID), `name` (string), `character_class` (string, nullable), `level` (int, default 1), `xp` (int, default 0), `hp` (int), `max_hp` (int), `prestige_count` (int, default 0), `current_location` (string reference, nullable), `milestones` (set of strings), `statistics` (PlayerStatistics dataclass with enemy/location/adventure counters), `stacks` (mapping of item ref to quantity for stackable items), `instances` (list of `ItemInstance` objects for non-stackable items, each with `instance_id: UUID`, `item_ref: str`, and `modifiers: Dict`), `equipment` (mapping of slot name to `instance_id: UUID`), `active_quests` (mapping of quest ref to stage name), `completed_quests` (set of quest refs), `active_adventure` (nullable adventure position struct), and `pending_triggers` (FIFO list of trigger names awaiting drain, default empty list).

In addition to fixed fields, the player state SHALL contain a `stats` mapping (stat name → value) populated dynamically from the `CharacterConfig` manifest at character creation. Both `public_stats` and `hidden_stats` are stored in this single mapping; the distinction is only presentational. Stat values SHALL be typed `int | bool | None` — the `float` type is no longer permitted. Stat values SHALL default to the declared default, or `null` if no default is set. Integer stats SHALL only be mutated through `CharacterState.set_stat()`, which enforces hard INT32 floor/ceiling bounds.

#### Scenario: New player starts with default values

- **WHEN** a new player state is created with only a name
- **THEN** level is 1, XP is 0, prestige_count is 0, milestones is empty, statistics has all counters at zero, stacks is empty, instances is empty, equipment is empty, active_adventure is None, pending_triggers is an empty list, and the stats map contains every stat from CharacterConfig initialised to its declared default

#### Scenario: Public stats are visible, hidden stats are not

- **WHEN** the player status panel is rendered
- **THEN** only stats declared under `public_stats` in CharacterConfig are displayed; stats in `hidden_stats` are omitted from the UI

#### Scenario: Stats map contains only int and bool values

- **WHEN** a character is created from a `CharacterConfig` that declares only `int` and `bool` stats
- **THEN** every value in `player.stats` is an `int`, `bool`, or `None`; no `float` values are present
